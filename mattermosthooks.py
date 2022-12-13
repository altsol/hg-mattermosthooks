# -*- coding: utf-8 -*-
import sys
import traceback
import requests
import json

from collections import namedtuple
from mercurial.logcmdutil import changesetdisplayer


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


def get_config(ui):
    webhook_url = ui.config(config_group, b'webhook_url').decode('utf-8')
    repo_name = ui.config(config_group, b'repo_name', default=None)
    commit_url = ui.config(config_group, b'commit_url', default=None)
    username = ui.config(config_group, b'username', default="mercurial")
    icon_emoji = ui.config(config_group, b'icon_emoji', default=None)
    icon_url = ui.config(config_group, b'icon_url', default=None)

    if repo_name is not None:
       repo_name = repo_name.decode('utf-8')
    if commit_url is not None:
       commit_url = commit_url.decode('utf-8')
    if icon_emoji is not None:
       icon_emoji = icon_emoji.decode('utf-8')
    if icon_url is not None:
       icon_url = icon_url.decode('utf-8')

    return Config(webhook_url, repo_name, commit_url, username, icon_emoji, icon_url)


def pushhook(node, hooktype, url, repo, source, ui, **kwargs):
    try:
        username = ui.username().decode('utf-8')
        config = get_config(ui)

        changesets = get_changesets(repo, node)
        count = len(changesets)
        messages = render_changesets(ui, repo, changesets, config).decode('utf-8')

        ensure_plural = "s" if count > 1 else ""
        ensure_repo_name = " to \"{0}\"".format(config.repo_name) if config.repo_name else ""

        text = "{user} pushes {count} changeset{ensure_plural}{ensure_repo_name}:\n{changes}".format(
            user=username,
            count=count,
            ensure_plural=ensure_plural,
            ensure_repo_name=ensure_repo_name,
            changes=messages)

        post_message_to_mattermost(text, config)
    except Exception:
        traceback.print_exc(file=sys.stdout)


def get_changesets(repo, node):
    node_rev = repo[node].rev()
    tip_rev = repo[b'tip'].rev()
    return range(tip_rev, node_rev - 1, -1)


def render_changesets(ui, repo, changesets, config):
    if config.commit_url is not None:
        node_template = "<{commit_url}{{node|short}}|{{node|short}}>".format(commit_url=config.commit_url)
    else:
        node_template = "{node|short}"

    template = "{0}: ```{1}```\\n".format(node_template, " | ".join([
        "{branch}",
        "{date(date, '%Y-%m-%d [%H:%M:%S]')}",
        "{desc|strip|firstline}",
        # "{desc}",
    ])).encode('utf-8')

    displayer = changesetdisplayer(ui, repo, {b'template': template})
    ui.pushbuffer()
    for rev in changesets:
        displayer.show(repo[rev])
    return ui.popbuffer()


def post_message_to_mattermost(message, config):
    payload = {
        'text': message,
        'username': config.username,
    }
    payload_optional_key(payload, config, 'icon_url')
    payload_optional_key(payload, config, 'icon_emoji')
    encoded_payload = json.dumps(payload)
    encoded_payload = "payload={0}".format(encoded_payload)
    requests.post(config.webhook_url, data=encoded_payload, headers={'Content-Type': 'application/x-www-form-urlencoded'})


def payload_optional_key(payload, config, key):
    value = config.__getattribute__(key)
    if value:
        payload[key] = value
