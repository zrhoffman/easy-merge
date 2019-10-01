import getpass
from gitlab import Gitlab  # package is named python-gitlab
from gitlab.v4.objects import ProjectManager, Project, ProjectMergeRequestManager, ProjectMergeRequest
from github import Github, Repository, PullRequest, GitRef  # package is named PyGithub
import keyring
from keyring.backends.SecretService import Keyring
import time


class Merger:
    TOKEN_SERVICE = 'Easy Merge'  # in the keyring, the group that the token is in
    TOKEN_NAME = 'Unimplemented'

    def __init__(self, remote_host):
        self.remote_host = remote_host

        self.userKeyring = keyring.get_keyring()  # type: Keyring
        self.token = self.userKeyring.get_password(self.TOKEN_SERVICE, self.TOKEN_NAME)
        self.api = None

    def set_token(self):
        token = getpass.getpass(self.TOKEN_NAME + ': ')  # type: str
        if isinstance(token, str) and len(token) > 0:
            self.userKeyring.set_password(self.TOKEN_SERVICE, self.TOKEN_NAME, token)

        return token

    @staticmethod
    def merge_method(squash: bool):
        if squash is True:
            merge_method = 'squash'
        else:
            merge_method = 'merge'

        return merge_method


class GitlabMerger(Merger):
    TOKEN_NAME = 'GitLab token'

    def connect_api(self, max_tries: int = 3):
        token = self.token

        # user gets max_tries tries to get the token correct
        tries = 0
        success = False

        gl = None

        while not success and tries < max_tries:
            try:
                if not (isinstance(token, str) and len(token) > 0):
                    raise Exception('Invalid token')
                gl = Gitlab(url=self.remote_host, private_token=token)  # type: Gitlab
                gl.auth()
                success = True
            except Exception:
                tries += 1
                token = self.set_token()

        if not success:
            print('Could not validate ' + self.TOKEN_NAME + '.')
            quit()

        self.api = gl

    def merge(self, remote_path: str, title: str, description: str, source_branch: str, target_branch: str,
              squash: bool, merge: bool):
        merge_method = self.merge_method(squash)

        projects = self.api.projects  # type: ProjectManager
        project = projects.get(remote_path)  # type: Project

        merge_requests = project.mergerequests  # type: ProjectMergeRequestManager

        merge_request = merge_requests.create(
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
            merge_request.merge()
            print('Merged by ' + merge_method + ' method')
        else:
            print('Skipping merge')


class GithubMerger(Merger):
    TOKEN_NAME = 'GitHub token'

    def connect_api(self, max_tries: int = 3):
        token = self.token

        # user gets max_tries tries to get the token correct
        tries = 0
        success = False
        gh = None

        while not success and tries < max_tries:
            try:
                if not (isinstance(token, str) and len(token) > 0):
                    raise Exception('Invalid token')
                gh = Github(login_or_token=token, base_url=self.remote_host)
                success = True
            except Exception:
                tries += 1
                token = self.set_token()

            if not success:
                raise Exception('Could not validate ' + self.TOKEN_NAME + '.')

            self.api = gh

    def merge(self, remote_path: str, title: str, description: str, source_branch: str, target_branch: str,
              squash: bool, merge: bool):
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
            pull.merge(merge_method=merge_method)  # type: bool
            print('Merged by ' + merge_method + ' method')
            source_ref = repo.get_git_ref('heads/' + source_branch)  # type: GitRef
            source_ref.delete()
            print('Deleted source branch ' + source_branch)
        else:
            print('Skipping merge')
