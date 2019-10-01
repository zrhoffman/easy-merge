#!/usr/bin/env python3

import argparse, getpass, keyring, re, requests, subprocess, time, urllib
from argparse import Namespace, ArgumentParser
from github import Github, AuthenticatedUser, PaginatedList, Repository, PullRequest, Branch, \
    GitRef  # package is named PyGithub
from gitlab import Gitlab, GitlabHttpError  # package is named python-gitlab
from gitlab.v4.objects import ProjectManager, Project, ProjectMergeRequestManager, ProjectMergeRequest, ProjectBranch
from keyring.backends.SecretService import Keyring
from re import Pattern
from requests import Response
from subprocess import check_output


class Merger:
    TOKEN_SERVICE = 'Easy Merge'  # in the keyring, the group that the token is in
    TOKEN_NAME = 'Unimplemented'

    def __init__(self, remote_host):
        self.remote_host = remote_host

    def loadToken(self):
        self.userKeyring = keyring.get_keyring()  # type: Keyring
        self.token = self.userKeyring.get_password(self.TOKEN_SERVICE, self.TOKEN_NAME)

    def setToken(self):
        token = getpass.getpass(self.TOKEN_NAME + ': ')  # type: str
        if isinstance(token, str) and len(token) > 0:
            self.userKeyring.set_password(self.TOKEN_SERVICE, self.TOKEN_NAME, token)

        return token

    def merge_method(self, squash: bool):
        if squash == True:
            merge_method = 'squash'
        else:
            merge_method = 'merge'

        return merge_method


class GithubMerger(Merger):
    TOKEN_NAME = 'GitHub token'

    def connect_api(self, max_tries=3):
        token = self.token

        # user gets max_tries tries to get the token correct
        tries = 0
        success = False
        gh = None

        while success == False and tries < 3:
            try:
                if not (isinstance(token, str) and len(token) > 0):
                    raise Exception('Invalid token')
                gh = Github(login_or_token=token, base_url=self.remote_host)
                success = True
            except Exception:
                tries += 1
                token = merger.setToken()

            if success == False:
                raise Exception('Could not validate ' + self.TOKEN_NAME + '.')

            self.api = gh

    def merge(self, remote_path, title, scription, source_branch, target_branch, squash, merge: bool):
        merge_method = self.merge_method(squash)

        repo = self.api.get_repo(remote_path)  # type: Repository
        pull = repo.create_pull(
            title=title,
            body=description,
            head=source_branch,
            base=target_branch,
            maintainer_can_modify=True
        )  # type: PullRequest
        print('Created pull request!')

        if merge:
            print('Waiting to merge (because GitHub\'s API is slow)...')
            time.sleep(1)
            print('Finished waiting.')
            result = pull.merge(merge_method=merge_method)  # type: bool
            print('Merged by ' + merge_method + ' method')
            source_ref = repo.get_git_ref('heads/' + source_branch)  # type: GitRef
            source_ref.delete()
            print('Deleted source branch ' + source_branch)
        else:
            print('Skipping merge')



class GitlabMerger(Merger):
    TOKEN_NAME = 'GitLab token'

    def connect_api(self, max_tries=3):
        token = self.token

        # user gets max_tries tries to get the token correct
        tries = 0
        success = False
        gl = None

        while success == False and tries < 3:
            try:
                if not (isinstance(token, str) and len(token) > 0):
                    raise Exception('Invalid token')
                gl = Gitlab(url=self.remote_host, private_token=token)  # type: Gitlab
                gl.auth()
                success = True
            except Exception:
                tries += 1
                token = merger.setToken()

        if success == False:
            print('Could not validate ' + self.TOKEN_NAME + '.')
            quit()

        self.api = gl

    def merge(self, remote_path, title, description, source_branch, target_branch, squash, merge: bool):
        merge_method = self.merge_method(squash)

        projects = self.api.projects  # type: ProjectManager
        project = projects.get(remote_path)  # type: Project

        mergerequests = project.mergerequests  # type: ProjectMergeRequestManager

        mergeRequest = mergerequests.create(
            {
                'source_branch': source_branch,
                'target_branch': target_branch,
                'title': title,
                'description': description,
                'remove_source_branch': True,
                'squash': squash,
            }
        )  # type: ProjectMergeRequest

        print('Created pull request!')

        if merge:
            result = mergeRequest.merge()
            print('Merged by ' + merge_method + ' method')
        else:
            print('Skipping merge')


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

    parser = argparse.ArgumentParser(description='Merge branches in git easily')  # type: ArgumentParser
    parser.add_argument('-s', '--source', type=str, help='The source branch to merge from')
    parser.add_argument('-d', '--dest', type=str, help='The destination branch to merge to')
    parser.add_argument('-t', '--title', type=str, help='The title of the merge request')
    parser.add_argument('--description', type=str, help='The description (body) of the merge request')
    parser.add_argument('-n', '--no-squash', action='store_true', help='If set, do not squash merged commits.')
    parser.add_argument('-e', '--no-merge', action='store_true', help='If set, do not merge the merge request')

    # this is up here rather than later because we want to fail early if input does not validate
    args = parser.parse_args()  # type: Namespace

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

    squash = not args.no_squash

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

    should_merge = not args.no_merge
    merger.merge(remote_path, title, description, source_branch, target_branch, squash, should_merge)

    subprocess.call(['git', 'fetch', remote])
    subprocess.call(['git', 'branch', '-D', target_branch])
    subprocess.call(['git', 'checkout', '--merge', '--track', remote + '/' + target_branch])
    subprocess.call(['git', 'branch', '-D', source_branch])
