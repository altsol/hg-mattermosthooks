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
        'webhook_url',
        'branches',
        'commit_url',
        'username',
        'icon_emoji',
        'icon_url',
    ])


def get_teams(ui):
    yield 'default'
    for field, value in ui.configitems(config_group):
        if '.webhook_url' in field:
            assert len(field) > len('.webhook_url'), 'Mattermost team configuration error'
            yield field.split('.')[0]


def get_config(ui, team):
    get_field = lambda field: '{team_with_separator}{field}'.format(
        team_with_separator='' if team == 'default' else '{}.'.format(team),
        field=field
    )
    return Config(
        webhook_url = ui.config(
            config_group, get_field('webhook_url')),

        branches = ui.configlist(
            config_group, get_field('branches')),

        commit_url = ui.config(
            config_group, 'commit_url', default=None),

        username = ui.config(
            config_group, 'username', default=ui.username()),

        icon_emoji = ui.config(
            config_group, 'icon_emoji', default=None),

        icon_url = ui.config(
            config_group, 'icon_url', default=None)
    )


def pushhook(node, hooktype, url, repo, source, ui, **kwargs):
    '''Every team has its own configuration'''
    for team in get_teams(ui):
        publish(node, repo, ui, team)


def publish(node, repo, ui, team):
    config = get_config(ui, team)
    changesets = get_changesets(repo, node, config.branches)
    count = len(changesets)
    if not count:
        return
    # filter some characters that cause http 400 response
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

    post_message_to_mattermost(text, config, team)


def get_changesets(repo, node, branches):
    '''
    Team may share same repository with other team,
    thus filter team specific branches,
    otherwise don't filter
    '''
    node_rev = repo[node].rev()
    tip_rev = repo['tip'].rev()

    def belongs_team(branch):
        # pass any revision branch when team branches not configured
        if not branches:
            return True
        # verify revision branch conforms to team configured branches
        return any(
            team_branch in branch
            for team_branch in branches
        )

    return [
        rev
        for rev in range(tip_rev, node_rev - 1, -1)
        if belongs_team(repo[rev].branch())
    ]


def render_changesets(ui, repo, changesets, config):
    url = "{}/{}/rev/".format(config.commit_url, os.path.basename(repo.root))
    if config.commit_url:
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
    request = urllib2.Request(
        config.webhook_url,
        "payload={0}".format(json.dumps(payload))
    )
    urllib2.build_opener().open(request)


def payload_optional_key(payload, config, key):
    value = config.__getattmainprojectute__(key)
    if value:
        payload[key] = value
