from flask import Flask, request
import threading
from multiprocessing import Pool, Process
import logging
from pathlib import Path
import re
import os
import ast
import requests
import shutil
from time import sleep, time
import json
import datetime
from scripts import config
from urllib.parse import quote
import git

log = logging.getLogger(__name__)


class EndpointUrls:
    """Setting global endpoint accesses"""
    def __init__(self, organization, repository):
        self.api_url = "https://try.gitea.io/api/v1/"
        self.org_url = self.api_url + organization
        self.org_repo_list = self.api_url + "orgs/" + organization + "/repos"
        self.repo_url = self.api_url + "repos/" + organization + "/" + repository
        self.repo_branches = self.repo_url + "/branches"
        self.repo_branches_protections = self.repo_url + "/branch_protections"
        self.repo_id = "full_name"
        self.branch = None
        self.protected_branch = None
        self.teams_search = self.api_url + "orgs/teams/search"
        self._token = os.environ['GITEA_TOKEN']
        self.url_token = "?token=" + self._token
        self.verify = self.set_verify()

    def set_verify(self):
        """Change verify ssl for test server"""
        if "ch03test" in self.api_url:
            return False
        else:
            return True

    def set_branch(self, branch):
        """Will set a branch url"""
        self.branch = self.repo_branches + "/" + branch
        # Beware of the special web characters :
        safe_branch = quote(branch, safe='')
        self.protected_branch = self.repo_branches_protections + "/" + safe_branch


class Failure(Exception):
    """ Wrap standard exception to add a http status code."""

    def __init__(self, message, status_code):
        """ Constructor
        Args:
            message(str): error message
            status_code(int): http status code
        """
        Exception.__init__(self)
        self.message = message
        self.status_code = status_code


class BranchPush(threading.Thread):
    """Use a thread to call a branch"""
    def __init__(self, handler, branch):
        threading.Thread.__init__(self)
        self.handler = handler
        self.branch = branch

    def run(self):
        sleep(0.1)
        self.handler.protect_branch(self.branch)
        self.handler.update_branches()


class BranchList(threading.Thread):
    """Use a thread to call a branch"""
    def __init__(self, handler):
        threading.Thread.__init__(self)
        self.handler = handler

    def run(self):
        self.handler.update_branches()


class RepositoryHandler:
    """ this doc"""
    def __init__(self, organization, repository):
        self.organization = organization
        self.repository = repository
        self.parameters = config.ConfigReader(organization)
        self.repo_parameters = self.parameters.config_get(repository)
        self.urls = EndpointUrls(organization, repository)
        self.branches = []
        self.protected_branches = []
        self.read_branches()
        self.identity = organization + "/" + repository

    def get_branches(self, protected=False):
        """Recover the protected branches"""
        next_page_exists = True
        page = 1
        all_branches = []
        count = 0
        url = self.urls.repo_branches
        to_append = "name"
        if protected:
            url = self.urls.repo_branches_protections
            url += self.urls.url_token
            to_append = "branch_name"
        while next_page_exists:
            params = {"per_page": 100, "page": page}
            print("{} grabbed page {}".format(self.repository, page))
            # print('processing repo page {}'.format(page))
            r = requests.get(url, params=params, verify=self.urls.verify)
            json_branches = r.json()
            if r.status_code != 200:
                count += 1
                # print("Incorrect status code - sleeping")
                # print(r.text)
                sleep(0.1)
                if count == 3:
                    # print("too much errors - skipping")
                    next_page_exists = False
            else:
                # print(pull_api_url)
                # print(r.links)
                page += 1
                for branch in json_branches:
                    all_branches.append(branch[to_append])
                if page % 100 == 0:
                    sleep(0.3)
                    # print("prevent bottleneck")
                if "next" not in r.links:
                    next_page_exists = False
                    # print('finished fetching branches')
        return all_branches

    def is_branch_in_regex(self, ref_branch):
        """Parse the regex in the config and compare it to a given branch"""
        regexed_branches = ast.literal_eval(self.repo_parameters["branches"])
        for regex in regexed_branches:
            is_concerned = re.match(regex, ref_branch)
            if is_concerned:
                return True
        return False

    def is_branch_protected(self, branch):
        if branch in self.protected_branches:
            return True
        else:
            return False

    def is_branch_exists(self, branch):
        if branch in self.branches:
            return True
        else:
            return False

    def update_branches(self):
        """Will reupdate the file with new server status"""
        self.branches = self.get_branches()
        self.protected_branches = self.get_branches(protected=True)
        self.save_branches_to_file()

    def save_branches_to_file(self):
        """Write protected branches to file"""
        branches_filename = self.organization + "_" + self.repository + "_branches.txt"
        protected_branches_filename = self.organization + "_" + self.repository + "_protected_branches.txt"
        files = {branches_filename: self.branches, protected_branches_filename: self.protected_branches}
        for file, to_save in files.items():
            saving = open(file, "w")
            print(to_save)
            saving.write(str(to_save))
            saving.close()
            print("Written {} to disk".format(file))
            sleep(0.5)
        print("Saving done")

    def read_branches(self):
        """Reading branches from file"""
        print("Checking branches")
        branches_filename = self.organization + "_" + self.repository + "_branches.txt"
        protected_branches_filename = self.organization + "_" + self.repository + "_protected_branches.txt"
        already_loaded = os.path.isfile(branches_filename)
        already_loaded_protected = os.path.isfile(protected_branches_filename)
        if not already_loaded or not already_loaded_protected:
            print("Getting branches")
            self.update_branches()
            # print(self.branches)
            # print(self.protected_branches)
            self.save_branches_to_file()
        print("Reading files")
        files = {branches_filename: self.branches, protected_branches_filename: self.protected_branches}
        for file in files.keys():
            reading = open(file, "r")
            to_read = reading.readlines()[0]
            files[file] = to_read
            # to_read = ast.literal_eval(read_file)
            print("Read {} from disk".format(file))
            print("found ", to_read)
            reading.close()
        self.branches = files[branches_filename]
        self.protected_branches = files[protected_branches_filename]
        if self.branches == "" or self.branches == []:
            print("!! EMPTY BRANCHES !!")
            try:
                print('removing Files')
                os.remove(branches_filename)
                os.remove(protected_branches_filename)
            except Exception as e:
                print('Cannot reset configuration {}'.format(e))
            print("Missing branches - Check {} Repository {}".format(self.organization, self.repository))
            raise Failure("failed", 500)

    def protect_branch(self, branch):
        """ Make an api call to protect the branch"""
        # set the dictionary with parameters
        action_dict = {}
        for k, v in self.repo_parameters.items():
            if k != "branches":
                try:
                    action_dict[k] = ast.literal_eval(v)
                except ValueError:
                    # ensure Json boolean
                    if v == "true":
                        action_dict[k] = True
                    elif v == "false":
                        action_dict[k] = False
                    else:
                        action_dict[k] = v
        action_dict["branch_name"] = branch
        # set the specifics for this branch
        self.urls.set_branch(branch)
        action = requests.post
        url = self.urls.repo_branches_protections
        # if we need to modify the branch protection then set up another url
        if self.is_branch_protected(branch):
            action = requests.patch
            url = self.urls.protected_branch
            # if the protection exists, we don't need this key
            action_dict.pop("branch_name")
        url += self.urls.url_token
        headers = {'content-type': 'application/json', 'accept': 'application/json'}
        r = action(url, data=json.dumps(action_dict), headers=headers, verify=self.urls.verify)
        # Should get a 201
        correct_answer = [200, 201]
        if r.status_code not in correct_answer:
            print("ERROR")
            print(r.url)
            print(r.status_code)
            print(r.text)
            print(action_dict)
            print("----------------")
            raise Failure(r.text, r.status_code)
        else:
            print("{} protected on {}".format(branch, self.identity))
            # self.protected_branches.append(branch)
            # self.branches.append(branch)


class FlaskHook:
    def __init__(self):
        self.base = os.getcwd()
        self.organizations = []
        self.repositories = {}
        self.handlers = []
        self.indexes = []
        self.find_organizations()
        self.make_handlers()
        self.thread_list = []

    def find_organizations(self):
        """Find ini files and populate"""
        print("found organizations : ")
        for file in Path(self.base).glob('**/*.ini'):
            print(file.name)
            self.organizations.append(file.stem)

    def reset(self):
        self.__init__()

    @staticmethod
    def populate_repository(organization):
        org_config = config.ConfigReader(organization)
        org_config.config_read()
        return org_config.sections

    def make_handlers(self):
        for org in self.organizations:
            self.repositories[org] = self.populate_repository(org)
        for key, value in self.repositories.items():
            for v in value:
                self.handlers.append(RepositoryHandler(key, v))
        for handler in self.handlers:
            self.indexes.append(handler.identity)

    def refresh_handler(self, organization, full_name):
        self.repositories[organization] = self.populate_repository(organization)
        for key, value in self.repositories.items():
            for v in value:
                self.handlers.append(RepositoryHandler(key, v))
        for handler in self.handlers:
            self.indexes.append(handler.identity)

    def is_in_indexes(self, full_name):
        if full_name in self.indexes:
            for handler in self.handlers:
                if handler.identity == full_name:
                    return True, handler
        else:
            return False, None


def create_app():
    """ Create Flask application.
    Check config.ini, returns correct addresses
    Returns:
        flask.App: A flask application instance.
    """
    app = Flask(__name__, instance_relative_config=False)
    app.logger.setLevel(logging.INFO)  # pylint: disable=no-member

    logging.basicConfig(level=os.environ.get("LOGLEVEL", "INFO"))
    # app.run(host='0.0.0.0', port=6001, threaded=True, debug=False)
    # log = logging.getprint(__name__)
    hooks = FlaskHook()
    task_list = []
    print("Waiting input")
    # print("Waiting input")

    def update_handlers():
        handlers_update = []
        for handler in hooks.handlers:
            handlers_update.append(BranchList(handler))
        for thread in handlers_update:
            thread.start()
        for thread in handlers_update:
            thread.join()
        hooks.make_handlers()

    def threads_works():
        """Empty the tasks"""
        if len(task_list) > 0:
            for thread in task_list:
                if not thread.is_alive():
                    try:
                        thread.start()
                    except Exception as e:
                        print("Thread already started probably {}".format(e))
        while len(task_list) > 0:
            for thread in task_list:
                thread.join()
            for thread in task_list:
                task_list.remove(thread)

    @app.route('/branch_protection/list', methods=['GET'])
    def list_repo():
        """Display config file"""
        pretty_print = {}
        for handler in hooks.handlers:
            pretty_print[handler.identity] = handler.protected_branches
        return json.dumps(pretty_print)

    @app.route('/branch_protection/push_list', methods=['GET'])
    def push_repo():
        """Push every repo in the config list - do not alter existing branches"""
        for handler in hooks.handlers:
            for branch in handler.branches:
                if handler.is_branch_in_regex(branch) and not handler.is_branch_protected(branch):
                    task_list.append(BranchPush(handler, branch))
        threads_works()
        update_handlers()
        print("Please reload the script : http://yourport:yoururl/branch_protection/reload ")
        return "200 - {}".format("mirror")

    @app.route('/branch_protection/force_push_list', methods=['GET'])
    def force_push_repo():
        """Force push every repo in the config list - alter existing branches so that they renew protection"""
        for handler in hooks.handlers:
            for branch in handler.branches:
                if handler.is_branch_in_regex(branch):
                    task_list.append(BranchPush(handler, branch))
        threads_works()
        print("Please reload the script : http://yourport:yoururl/branch_protection/reload ")
        update_handlers()
        return "200 - {}".format("mirror")

    @app.route('/branch_protection/reload', methods=['GET'])
    def reload_repo():
        """Reload the full class"""
        actual_project = git.Repo("")
        actual_project.git.reset('--hard')
        pull_project = actual_project.remotes.origin
        pull_project.pull()
        actual_project.git.reset('--hard')
        for file in Path().glob('**/*.txt'):
            print("deleting {}".format(file.name))
            os.remove(file)
        hooks.reset()
        # exit("0")
        return '200 - Reread'

    @app.route('/branch_protection/webhook', methods=['GET', 'POST'])
    def webhook():  # pylint: disable=unused-variable
        """ Handle gitlab webhook
        Returns:
            flask.Response: An http response
        """
        # print("incoming request")
        null_value = "0" * 16
        if request.method == "GET":
            threads_works()
            return '200 OK'
        if request.method == 'POST':
            file = open("webhook.txt", 'a')
            # threads_works()
            request_json = request.get_json()
            headers = request.headers
            file.write(str(request_json))
            file.write("\n")
            file.write(str(headers))
            file.write("\n")
            file.close()
            try:
                print(headers.get("X-Gitea-Event"))
            except Exception as e:
                print(e)
            repo_http_url = full_name = repo_branch = repo_name = ""
            push_type = None
            before = None
            try:
                print("Incoming POST")
                repo_http_url = request_json[u'repository'][u'html_url']
                full_name = request_json[u'repository'][u'full_name']
                repo_branch = request_json[u'ref'].replace("refs/heads/", "")
                repo_name = request_json[u'repository'][u'name']
                if "u'after'" in request_json.keys():
                    push_type = request_json[u'after']
                if "u'before'" in request_json.keys():
                    before = request_json[u'before']

                event = headers.get("X-Gitea-Event")
                str_obj = "{}, {}, {}, {}, {}".format(
                    str(repo_name),
                    str(full_name),
                    str(repo_branch),
                    str(repo_http_url),
                    str(push_type)
                )
                log.info(str_obj)
            except KeyError as e:
                log.error("Webhook not expecting this post \n {}".format(e))
                return "500 - Not expected"
            else:
                check, handler = hooks.is_in_indexes(full_name)
                if check is True:
                    watch = handler.is_branch_in_regex(repo_branch)
                    # log.info(push_type, before)
                    # log.info(before)
                    # log.info(repo_branch)
                    # log.info(handler)
                    if watch is True:
                        # print("Will add {}".format(repo_branch))
                        if repo_branch not in handler.protected_branches and event != "delete":
                            task_list.append(BranchPush(handler, repo_branch))
                            log.info("Appending {} to the protection {}".format(repo_branch, handler.identity))
                    p = Process(target=lambda: threads_works())
                    p.start()
                    # Grab deleted ones
                return "200 - OK"

    @app.route('/branch_protection/hello', methods=['GET'])
    def hello():  # pylint: disable=unused-variable
        """ Returns "Hello World!" to test if the service is alive.
        Returns:
            flask.Response: An http response
        """
        return 'Hello World!'

    return app


if __name__ == "__main__":
    # logging.getLogger().setLevel(logging.INFO)
    app = create_app()
    app.logger.setLevel(logging.INFO)
    app.run(host='0.0.0.0', port=6000, threaded=True, debug=False)