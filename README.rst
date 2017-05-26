hg-mattermosthooks
=============

Mercurial server-side hooks for Mattermost messaging service. Multiple repositories with shared project branches support.

Examples
~~~~~~~~

To add push hooks for some repo, modify ``.hg/hgrc`` in the central repository::

    [mattermosthooks]
    webhook_url = DEFAULT_WEBHOOK_URL
    sideproject.webhook_url = SIDEPROJECT_WEBHOOK_URL
    sideproject.branches = feature392, feature513
    commit_url = http://mercurial.example.com:8008
    icon_url = http://example.com/mercurial.png

    [hooks]
    changegroup.mattermosthooks= python:/path/to/mattermosthooks.py:pushhook

You may put as many sideprojects as null or more. Teams are found by ``.webhook_url`` substring. Separate config arranged for every team.

Example of chat message output:

.. image:: http://i.imgur.com/HiWNywS.png
    :alt: Mercurial push hook chat message
    :align: center

Options
~~~~~~~

#. ``webhook_url`` is your unique webhook URL. *Required* field for the main project.
#. ``branches`` string of comma-separated values, use quotes for values with spaces. Skip this option to show all revisions from all branches.
#. ``commit_url`` is a part of URL for particular changeset. If it is specified, link to a changeset will be inserted in description of changeset. Plain text short revision number will be used otherwise.
#. ``username`` is the displayed name. Defaults to username configured in remote repository
#. ``icon_emoji`` is the name of emoticon, which will be displayed. *Optional and not yet supported by Mattermost.* You can use ``icon_url`` instead.
#. ``icon_url`` is a direct link to image, which will be displayed. *Optional.* You can use
   `this icon URL <https://raw.githubusercontent.com/altsol/hg-mattermosthooks/master/assets/mercurial.png>`_ if you want.

``icon_emoji`` and ``icon_url`` are both optional and interchangeable.

Credits
~~~~~~~

The source code is forked from https://github.com/oblalex/hg-slackhooks and https://github.com/virhilo/hg-slackhooks. Special thanks to the original authors for making this awesome hook for Mercurial. The main difference in this fork involves alternative handling of markdown construction in order to produce a better result in Mattermost.
