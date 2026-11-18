# -*- coding: utf-8 -*-
import re
import traceback
import requests
import json

from collections import namedtuple
from urllib.parse import unquote_to_bytes
from mercurial.utils.dateutil import datestr
from mercurial.utils.stringutil import person


config_group = b'mattermosthooks'
Config = namedtuple(
    'HgMattermostHooksConfig',
    field_names=[
        'webhook_url',
        'repo_name',
        'repo_url',
        'commit_url',
        'issue_url',
        'username',
        'icon_emoji',
        'icon_url',
        'color',
    ])

# Changeset sources that mean "someone pushed". Over hgweb or ssh the source is
# 'serve', for a push to a local path it is 'push'. Others ('strip' when hg
# restores a backup bundle, 'pull', 'unbundle', ...) are not announced.
PUSH_SOURCES = (b'serve', b'push')

# At most this many changesets are listed in one message.
MAX_CHANGESETS = 20

REQUEST_TIMEOUT = 10  # seconds

DEFAULT_COLOR = '#E8833A'

# Characters with a markdown meaning in Mattermost; escaped in commit messages.
MARKDOWN_CHARS = re.compile(r'([\\`*_~\[\]<>|])')
# '@user' / '@channel' would notify people and '~channel' links a channel. An
# invisible word joiner after the sign keeps the text but breaks the mention.
MENTIONS = re.compile(r'([@~])(?=\w)')
WORD_JOINER = '⁠'
# Redmine-style issue references: '#10901'.
ISSUE_REFS = re.compile(r'(?<![\w/&])#(\d+)\b')


def _decode(value):
    return value.decode('utf-8') if value is not None else None


def get_config(ui):
    def option(name):
        return _decode(ui.config(config_group, name))

    commit_url = option(b'commit_url')
    repo_url = option(b'repo_url')
    if repo_url is None and commit_url and commit_url.endswith('/rev/'):
        repo_url = commit_url[:-len('rev/')]  # hgweb: .../repo/rev/ -> .../repo/

    return Config(
        webhook_url=option(b'webhook_url'),
        repo_name=option(b'repo_name'),
        repo_url=repo_url,
        commit_url=commit_url,
        issue_url=option(b'issue_url'),
        username=option(b'username') or 'mercurial',
        icon_emoji=option(b'icon_emoji'),
        icon_url=option(b'icon_url'),
        color=option(b'color') or DEFAULT_COLOR,
    )


def warn(ui, message):
    ui.warn(('mattermosthooks: ' + message + '\n').encode('utf-8'))


def pushhook(node, hooktype, url, repo, source, ui, **kwargs):
    # Errors go through ui.warn: under hgweb, plain stdout never reaches the
    # pusher, while ui output is sent back as "remote:" lines.
    try:
        if source not in PUSH_SOURCES:
            return
        config = get_config(ui)
        if not config.webhook_url:
            warn(ui, 'webhook_url not configured, nothing posted')
            return

        changesets = get_changesets(repo, node, kwargs.get('node_last'))
        names = pusher_names(url, repo, changesets)
        post_message_to_mattermost(ui, build_attachment(repo, changesets, names, config), config)
    except requests.RequestException as e:
        warn(ui, 'failed to reach Mattermost: {0}'.format(e))
    except Exception:
        warn(ui, 'failed to notify Mattermost:\n' + traceback.format_exc())


def get_changesets(repo, node, node_last=None):
    """Revs of this push, newest first.

    node_last is used instead of tip: the hook runs after the lock is released,
    so tip may already include changesets of a later push."""
    node_rev = repo[node].rev()
    last_rev = repo[node_last].rev() if node_last else repo[b'tip'].rev()
    return range(last_rev, node_rev - 1, -1)


def pusher_names(url, repo, changesets):
    """[authenticated HTTP user] if there is one, else the unique changeset authors.

    ui.username() would be the server's user (e.g. www-data@host), not the pusher.
    For pushes over HTTP, url is b'remote:<scheme>:<host>:<user>' (quoted)."""
    parts = url.split(b':') if url else []
    if len(parts) == 4 and parts[0] == b'remote' and parts[3]:
        return [unquote_to_bytes(parts[3]).decode('utf-8', 'replace')]

    authors = []
    for rev in changesets:
        name = author(repo[rev])
        if name not in authors:
            authors.append(name)
    return authors


def join_names(names):
    """'A', 'A and B', 'A, B and C'."""
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def author(ctx):
    return person(ctx.user()).decode('utf-8', 'replace')


def build_attachment(repo, changesets, names, config):
    """The message as one Mattermost (Slack-compatible) attachment."""
    count = len(changesets)
    title = "{0} pushed {1} changeset{2}{3}".format(
        join_names(names), count, "s" if count > 1 else "",
        " to {0}".format(config.repo_name) if config.repo_name else "")

    shown = changesets[:MAX_CHANGESETS]
    lines = [format_changeset(repo[rev], names, config) for rev in shown]
    if count > len(shown):
        lines.append("… and {0} more".format(count - len(shown)))

    branches = []
    for rev in changesets:
        branch = repo[rev].branch().decode('utf-8', 'replace')
        if branch not in branches:
            branches.append(branch)

    attachment = {
        'fallback': title,
        'color': config.color,
        'title': title,
        'text': "\n".join(lines),
        'fields': [{
            'short': True,
            'title': "Branches" if len(branches) > 1 else "Branch",
            'value': ", ".join("`{0}`".format(b) for b in branches),
        }],
    }
    if config.repo_url:
        attachment['title_link'] = config.repo_url
    return attachment


def format_changeset(ctx, names, config):
    """'[hash](link) [`branch`] description · date[ · author]' as markdown."""
    short = ctx.hex()[:12].decode('ascii')
    if config.commit_url:
        node = "[{0}]({1}{0})".format(short, config.commit_url)
    else:
        node = "`{0}`".format(short)

    parts = [node]
    branch = ctx.branch().decode('utf-8', 'replace')
    if branch != 'default':
        parts.append("`{0}`".format(branch))
    description = ctx.description().decode('utf-8', 'replace').strip()
    parts.append(format_description(description.split('\n')[0], config.issue_url))

    line = " ".join(parts) + " · " + datestr(ctx.date(), b'%Y-%m-%d %H:%M').decode('ascii')
    name = author(ctx)
    if names != [name]:
        line += " · " + name
    return line


def format_description(text, issue_url=None):
    """A commit message line as safe markdown: no formatting, no mentions,
    and '#123' linked to issue_url when it is set."""
    text = MARKDOWN_CHARS.sub(r'\\\1', text)
    text = MENTIONS.sub(r'\1' + WORD_JOINER, text)
    if issue_url:
        text = ISSUE_REFS.sub(lambda m: "[#{0}]({1}{0})".format(m.group(1), issue_url), text)
    return text


def post_message_to_mattermost(ui, attachment, config):
    payload = {
        'username': config.username,
        'attachments': [attachment],
    }
    payload_optional_key(payload, config, 'icon_url')
    payload_optional_key(payload, config, 'icon_emoji')
    # Let requests URL-encode the form body: raw ';', '&', '+' or '%' in commit
    # messages otherwise break the form parsing on the Mattermost side (HTTP 400).
    response = requests.post(config.webhook_url, data={'payload': json.dumps(payload)},
                             timeout=REQUEST_TIMEOUT)
    if not response.ok:
        warn(ui, 'webhook returned HTTP {0}: {1}'.format(response.status_code, response.text))


def payload_optional_key(payload, config, key):
    value = getattr(config, key)
    if value:
        payload[key] = value
