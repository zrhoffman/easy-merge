import argparse
from argparse import ArgumentParser, Namespace

parser = argparse.ArgumentParser(prog='easy-merge', description='Create and merge merge requests in GitLab or GitHub easily') # type: ArgumentParser


def add_parameters():
    parser.add_argument('-s', '--source', type=str, help='The source branch to merge from')
    parser.add_argument('-d', '--dest', type=str, help='The destination branch to merge to')
    parser.add_argument('-t', '--title', type=str, help='The title of the merge request')
    parser.add_argument('--description', type=str, help='The description (body) of the merge request')
    parser.add_argument('-u', '--squash', action='store_true', help='If set, squash merged commits.')
    parser.add_argument('-e', '--merge', action='store_true', help='If set, merge the merge request after creating it.')


def get_arguments():
    return parser.parse_args()  # type: Namespace
