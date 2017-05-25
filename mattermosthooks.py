# -*- coding: utf-8 -*-
import urllib2
import json
import os
import re

from collections import namedtuple
from mercurial.cmdutil import show_changeset


config_group = 'mattermosthooks'
Config = namedtuple(
    'HgMattermostHooksConfig',
    field_names=[
        'webhook_urls',
        'repo_name',
        'commit_url',
        'username',
        'icon_emoji',
        'icon_url',
    ])


def get_config(ui):
    return Config(
        webhook_urls = dict(
            default=ui.config(
                config_group, 'webhook_url'
            ),
            myproject=ui.config(
                config_group, 'webhook_url_myproject', default=None
            )
        ),

        repo_name = ui.config(
	    config_group, 'repo_name', default=None),

        commit_url = ui.config(
	    config_group, 'commit_url', default=None),

        username = ui.config(
	    config_group, 'username', default="mercurial"),

        icon_emoji = ui.config(
	    config_group, 'icon_emoji', default=None),

        icon_url = ui.config(
	    config_group, 'icon_url', default=None)
    )


def pushhook(node, hooktype, url, repo, source, ui, **kwargs):
    config = get_config(ui)
    for team, changesets in get_changesets(repo, node).iteritems():
        count = len(changesets)
        messages = re.sub(
            '[;]', '',
            render_changesets(ui, repo, changesets, config)
        )

        ensure_plural = "s" if count > 1 else ""
        ensure_repo_name = " to \"{0}\"".format(os.path.basename(repo.root))

        text = "{user} pushes {count} changeset{ensure_plural}{ensure_repo_name}:\n{changes}".format(
            user=ui.username() or config.username,
            count=count,
            ensure_plural=ensure_plural,
            ensure_repo_name=ensure_repo_name,
            changes=messages)

        if count:
            post_message_to_mattermost(text, config, team)


def get_changesets(repo, node):
    node_rev = repo[node].rev()
    tip_rev = repo['tip'].rev()

    def belongs_myproject(branch_name):
        return any(
            myproject_branch_name in branch_name
            for myproject_branch_name in '''
                otherproject1
                otherproject2
                myproject
            '''.split()
        )

    changesets = dict(
        default = [
            rev
            for rev in range(tip_rev, node_rev - 1, -1)
            if not belongs_myproject(repo[rev].branch())
        ],
        myproject = [
            rev
            for rev in range(tip_rev, node_rev - 1, -1)
            if belongs_myproject(repo[rev].branch())
        ]
    )
    return changesets


def render_changesets(ui, repo, changesets, config):
    url = "http://192.168.200.69:8008/{}/rev/".format(os.path.basename(repo.root))
    if url:
        node_template = "<{url}{{node|short}}|{{node|short}}>".format(url=url)
    else:
        node_template = "{node|short}"

    template = "{0}: ```{1}```\\n".format(node_template, " | ".join([
        "{author|person}",
        "{branch}",
        "{date(date, '%Y-%m-%d [%H:%M:%S]')}",
        "{desc|strip|firstline}"
    ]))

    displayer = show_changeset(ui, repo, {'template': template})
    ui.pushbuffer()
    for rev in changesets:
        displayer.show(repo[rev])
    return ui.popbuffer()


def post_message_to_mattermost(message, config, team):
    payload = {
        'text': message,
        'username': config.username,
    }
    payload_optional_key(payload, config, 'icon_url')
    payload_optional_key(payload, config, 'icon_emoji')
    fmt = json.dumps(payload)
    # print fmt
    request = urllib2.Request(config.webhook_urls[team], "payload={0}".format(fmt))
    urllib2.build_opener().open(request)


def payload_optional_key(payload, config, key):
    value = config.__getattmainprojectute__(key)
    if value:
        payload[key] = value
