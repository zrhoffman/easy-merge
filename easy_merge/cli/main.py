#!/usr/bin/env python3
from argparse import Namespace

from . import arguments
import re, requests, subprocess
from re import Pattern
from ..mergers import GithubMerger, GitlabMerger
from subprocess import check_output


def is_json(host):
    try:
        match = is_json \
            .json_regex \
            .match(
            requests \
                .get(host + '/api/v4') \
                .headers['Content-Type']
        )
    except requests.exceptions.ConnectionError:
        match = False  # catches the edge case of attempting to resolve api.gitlab.com

    return match


def main():
    is_json.json_regex = re.compile(r'^application/json')

    arguments.add_parameters()

    # This is up here rather than later because we want to fail early if input does not validate
    args = arguments.get_arguments()  # type: Namespace

    remote = check_output(['git', 'remote']) \
        .decode('utf-8') \
        .strip() \
        .splitlines()[0] \
        .strip()  # type: str

    remote_url = check_output(
        ['git', 'config', '--get', 'remote.' + remote + '.url']
    ) \
        .decode('utf-8') \
        .strip()  # type: str

    # the URL of the repo
    remote_url = re.sub(
        r'^https?:\/+|^.*@',
        '',
        remote_url
    )

    remote_path = re.sub(
        r'^.*:|\.git$',
        r'',
        remote_url
    )

    # should be the hostname of a gitlab/github instance
    remote_host = re.search(
        pattern=r'([A-Za-z0-9\-\.]+)(:|/)',
        string=remote_url
    ).group(1)  # type: str

    gitlab_host = 'https://' + remote_host
    github_host = 'https://api.' + remote_host

    if is_json(github_host):
        # generate token at https://<github instance>/settings/tokens
        # give it repo::public_repo access (or the entire repo scope if you want private
        # repositories, too)
        merger = GithubMerger(github_host)
    elif is_json(gitlab_host):
        # generate token at https://<gitlabhost>/profile/personal_access_tokens
        # give it access to api, read_user, read_repository, and read_registry
        merger = GitlabMerger(gitlab_host)

    merger.loadToken()
    merger.connect_api()

    message = check_output(
        ['git', 'log', '--pretty=%B', '-n1']
    ) \
        .decode('utf-8') \
        .strip()  # type: str

    lines = message.splitlines()

    if args.title != None:
        title = args.title
    else:
        title = lines.pop(0)

    if args.description != None:
        description = args.description
    else:
        description = '\n'.join(
            map(
                str,
                lines
            )
        ).strip()

    squash = args.squash

    current_branch = check_output(['git', 'rev-parse', '--abbrev-ref', 'HEAD']) \
        .decode('utf-8') \
        .strip()  # type: str

    if args.source != None:
        source_branch = args.source
    else:
        source_branch = re.sub(
            pattern=r'\s+',
            repl='\xa0',  # non-breaking space
            string=message,
            flags=re.MULTILINE
        )  # type: Pattern

    # replace invalid character sequences with their unicode full-width equivalents
    # https://git-scm.com/docs/git-check-ref-format
    replacements = {
        "..": {
            "pattern": r'\.\.',
            "replacement": u'\uff0e\uff0e',
        },
        "^": {
            "pattern": r'\^',
            "replacement": u'\uff3e',
        },
        "~": {
            "pattern": r'~',
            "replacement": u'\uff5e',
        },
        "/": {
            "pattern": r'^/|/$',
            "replacement": u'\uff0f',
        },
        "//": {
            "pattern": r'//',
            "replacement": u'\uff0f\uff0f',
        },
        ":": {
            "pattern": r':',
            "replacement": u'\uff1a',
        },
        ".": {
            "pattern": r'^\.|\.$',
            "replacement": u'\uff0e',
        },
        "?": {
            "pattern": r'\?',
            "replacement": u'\uff1f',
        },
        "*": {
            "pattern": r'\*',
            "replacement": u'\uff0a',
        },
        "[": {
            "pattern": r'\[',
            "replacement": u'\uff3b',
        },
        "@{": {
            "pattern": r'@{',
            "replacement": u'@\uff5b',
        },
        "@": {
            "pattern": r'^@$',
            "replacement": u'\uff20',
        },
        "\\": {
            "pattern": r'\\',
            "replacement": u'\uff3c',
        },
    }

    for invalid_sequence, replacement_regex in replacements.items():
        source_branch = re.sub(
            pattern=replacement_regex['pattern'],
            repl=replacement_regex['replacement'],
            string=source_branch
        )

    if args.dest != None:
        target_branch = args.dest
    elif current_branch != source_branch:
        target_branch = current_branch
    else:
        target_branch = 'master'

    if source_branch != current_branch:
        subprocess.call(['git', 'checkout', '-b', source_branch])

    subprocess.call(['git', 'push', remote, source_branch])

    should_merge = args.merge
    merger.merge(remote_path, title, description, source_branch, target_branch, squash, should_merge)

    subprocess.call(['git', 'fetch', remote])
    subprocess.call(['git', 'branch', '-D', target_branch])
    subprocess.call(['git', 'checkout', '--merge', '--track', remote + '/' + target_branch])
    subprocess.call(['git', 'branch', '-D', source_branch])
