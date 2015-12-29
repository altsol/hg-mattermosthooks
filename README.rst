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
    icon_url = http://example.com/mercurial.png

    [hooks]
    changegroup.mattermosthooks= python:/path/to/mattermosthooks.py:pushhook

Example of chat message output:

.. image:: http://i.imgur.com/HiWNywS.png
    :alt: Mercurial push hook chat message
    :align: center

Options
~~~~~~~

#. ``webhook_url`` is your unique webhook URL.
#. ``repo_name`` is a name of your repository. *It's optional.*
#. ``commit_url`` is a part of URL for parcilular changeset. If it is specified, link to a changeset will be inserted in description of changeset. Plain text short revision number will be used otherwise.
#. ``username`` is the displayed name. Default: ``mercurial``.
#. ``icon_emoji`` is the name of emoticon, which will be displayed. *It's optional and not yet supported by Mattermost.* You can use ``icon_url`` instead.
#. ``icon_url`` is a direct link to image, which will be displayed. *It's optional.* You can use
   `this icon URL <https://raw.githubusercontent.com/altsol/hg-mattermosthooks/master/assets/mercurial.png>`_ if you want.

``icon_emoji`` and ``icon_url`` are both optional and interchangeable.

Credits
~~~~~~~

The source code is forked from https://github.com/oblalex/hg-slackhooks and https://github.com/virhilo/hg-slackhooks. Special thanks to the original authors for making this awesome hook for Mercurial. The main difference in this fork involves alternative handling of markdown construction in order to produce a better result in Mattermost.
