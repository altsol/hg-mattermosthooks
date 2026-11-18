hg-mattermosthooks
=============

Mercurial server-side hooks for Mattermost messaging service.

Examples
~~~~~~~~

To add push hooks for some repo, modify ``.hg/hgrc`` in the central repository::

    [mattermosthooks]
    webhook_url = WEBHOOK_URL
    repo_name = sample repository
    commit_url = http://example.com/101-sandbox/rev/
    issue_url = https://redmine.example.com/issues/
    icon_url = http://example.com/mercurial.png

    [hooks]
    changegroup.mattermosthooks= python:/path/to/mattermosthooks.py:pushhook

Each push is posted as one message card (a Slack-compatible message attachment) with a coloured side bar:

* the title says who pushed how many changesets to which repository and links to the repository;
* one line per changeset: short hash (linked to the changeset), branch when it is not ``default``,
  the first line of the commit message, the commit date, and the author when it differs from the title;
* a field with the branch(es) of the push.

At most 20 changesets are listed, followed by "… and N more". Commit messages are shown as plain text:
markdown characters are escaped and ``@mentions`` / ``~channel`` links are disabled, so a commit
message never notifies anyone. Only real pushes are announced (not strips, pulls or unbundles on the
server). Errors (e.g. Mattermost unreachable) are shown to the pusher as ``remote:`` lines and never
block the push.

Options
~~~~~~~

#. ``webhook_url`` is your unique webhook URL.
#. ``repo_name`` is a name of your repository. *It's optional.*
#. ``commit_url`` is a part of URL for particular changeset. If it is specified, link to a changeset will be inserted in description of changeset. Plain text short revision number will be used otherwise.
#. ``repo_url`` is the link of the message title. *It's optional.* If it is not set and ``commit_url`` ends with ``/rev/`` (hgweb), the repository URL is derived from it.
#. ``issue_url`` turns issue references like ``#123`` in commit messages into links to ``issue_url`` + ``123`` (e.g. ``https://redmine.example.com/issues/``). *It's optional.*
#. ``color`` is the colour of the card's side bar. Default: ``#E8833A``.
#. ``username`` is the displayed name. Default: ``mercurial``.
#. ``icon_emoji`` is the name of emoticon, which will be displayed. *It's optional and not yet supported by Mattermost.* You can use ``icon_url`` instead.
#. ``icon_url`` is a direct link to image, which will be displayed. *It's optional.* You can use
   `this icon URL <https://raw.githubusercontent.com/altsol/hg-mattermosthooks/master/assets/mercurial.png>`_ if you want.

``icon_emoji`` and ``icon_url`` are both optional and interchangeable.

Credits
~~~~~~~

The source code is forked from https://github.com/oblalex/hg-slackhooks and https://github.com/virhilo/hg-slackhooks. Special thanks to the original authors for making this awesome hook for Mercurial. The main difference in this fork involves alternative handling of markdown construction in order to produce a better result in Mattermost.
