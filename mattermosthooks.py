# -*- coding: utf-8 -*-
import traceback
import requests
import json

from collections import namedtuple
from urllib.parse import unquote_to_bytes
from mercurial.logcmdutil import changesetdisplayer
from mercurial.utils.stringutil import person


config_group = b'mattermosthooks'
Config = namedtuple(
    'HgMattermostHooksConfig',
    field_names=[
        'webhook_url',
        'repo_name',
        'commit_url',
        'username',
        'icon_emoji',
        'icon_url',
    ])

# Changeset sources that mean "someone pushed". Over hgweb or ssh the source is
# 'serve', for a push to a local path it is 'push'. Others ('strip' when hg
# restores a backup bundle, 'pull', 'unbundle', ...) are not announced.
PUSH_SOURCES = (b'serve', b'push')

# At most this many changesets are listed in one message.
MAX_CHANGESETS = 20

REQUEST_TIMEOUT = 10  # seconds


def _decode(value):
    return value.decode('utf-8') if value is not None else None


def get_config(ui):
    return Config(
        webhook_url=_decode(ui.config(config_group, b'webhook_url')),
        repo_name=_decode(ui.config(config_group, b'repo_name')),
        commit_url=_decode(ui.config(config_group, b'commit_url')),
        username=_decode(ui.config(config_group, b'username')) or 'mercurial',
        icon_emoji=_decode(ui.config(config_group, b'icon_emoji')),
        icon_url=_decode(ui.config(config_group, b'icon_url')),
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
        count = len(changesets)
        shown = changesets[:MAX_CHANGESETS]
        messages = render_changesets(ui, repo, shown, config).decode('utf-8')
        if count > len(shown):
            messages += "… and {0} more\n".format(count - len(shown))

        ensure_plural = "s" if count > 1 else ""
        ensure_repo_name = " to \"{0}\"".format(config.repo_name) if config.repo_name else ""

        names = pusher_names(url, repo, changesets)
        text = "{user} {verb} {count} changeset{ensure_plural}{ensure_repo_name}:\n{changes}".format(
            user=join_names(names),
            verb="push" if len(names) > 1 else "pushes",
            count=count,
            ensure_plural=ensure_plural,
            ensure_repo_name=ensure_repo_name,
            changes=messages)

        post_message_to_mattermost(ui, text, config)
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
        name = person(repo[rev].user()).decode('utf-8', 'replace')
        if name not in authors:
            authors.append(name)
    return authors


def join_names(names):
    """'A', 'A and B', 'A, B and C'."""
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def escape_template(text):
    """Make text literal inside an hg template ('\\' and '{' are special there)."""
    return text.replace('\\', '\\\\').replace('{', '\\{')


def render_changesets(ui, repo, changesets, config):
    if config.commit_url is not None:
        node_template = "<" + escape_template(config.commit_url) + "{node|short}|{node|short}>"
    else:
        node_template = "{node|short}"

    template = "{0}: ```{1}```\\n".format(node_template, " | ".join([
        "{branch}",
        "{date(date, '%Y-%m-%d [%H:%M:%S]')}",
        # a backtick would end the code span early, so it becomes a quote
        "{sub('`', \"'\", desc|strip|firstline)}",
    ])).encode('utf-8')

    displayer = changesetdisplayer(ui, repo, {b'template': template})
    ui.pushbuffer()
    for rev in changesets:
        displayer.show(repo[rev])
    return ui.popbuffer()


def post_message_to_mattermost(ui, message, config):
    payload = {
        'text': message,
        'username': config.username,
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
