# Gitea Branch Protection service

Small Python application to interact with Gitea repositories and protect Branches with regexes & wildcards

## How to launch ?

- Change the URL in app.py - line 24
- Create a token in Gitea, store it as an environment variable on the computer running the service (os.environ['GITEA_TOKEN'])
- Rename "myorganization.ini" to the name of your user in Gitea, or the organization you want to manage
- Launch with `./_bootstrap.sh` it should take care of itself
- Create a webhook in Gitea in your organization with "push, delete, create, release" events

Notes :
- You can dockerize this repository for an easy deployment
- The soft will store every branches into small text files in order to avoid punching the API on reload, this can be changed


## Config file for determining what to mirror: **name_of_organization**.ini ie : my_organization.ini

### Variables:
In the .ini file you'll have to make sure at least the following lines are filled: 
```
;-------------------------------------------------------------------
;   REPOSITORY
;-------------------------------------------------------------------
[*Repo_name*]
; regex for master/0.6 and similar : r"(master/.*)"
branches: [r"(master)", "mybranch"]
enable_push : true
enable_push_whitelist : true
enable_merge_whitelist : true
merge_whitelist_teams : ["Owners"] => Store here *existing* teams
push_whitelist_teams : ["Owners"] => Store here *existing* teams
block_on_rejected_reviews : true
required_approvals: 1
```

other possibilities for personalization:
see https://try.gitea.io/api/swagger#/repository/repoCreateBranchProtection

## Updating the repositories:

You need to reload the service in order for it to populate your changes
So if you edit the **repo_name**.ini file and push the modification to your server, then the mirror will auto update via the ["/reload" url](http://yourURL:yourport/branch_protection/reload) (see Utility urls)


## Utility urls:


the routes are configured like this (click to trigger) :

webhook: Entrypoint for the gitlab webhook

[hello](http://yourURL:yourport/branch_protection/hello): returns 200 Hello World

[list](http://yourURL:yourport/branch_protection/list): returns the actual protected branches per repository

[push_list](http://yourURL:yourport/branch_protection/push_list): Protect all branches following the rules that are found but not protected yet

[force_push_list](http://yourURL:yourport/branch_protection/force_push_list): Force protect all branches following the rules - useful if you changed behavior of existing branches

[reload](http://yourURL:yourport/branch_protection/reload): Repopulate the service with latest rules


## Branch Protection Webhook configuration
You just have to point a [*Gitea hook*](https://docs.gitea.io/en-us/webhooks/) to http://yourURL:yourport/branch_protection/webhook.

SSL is not loaded, and the hook can handle "push", "branches" actions and so on

## Notes about the code
### Regexes and config.ini
Actually the config.ini file returns string literals to the python code, then it is *evaluated* [with ast lib](https://docs.python.org/3/library/ast.html#ast.literal_eval).

That's why in order to parse them correctly, a choice was made to display them *"fully"*, like :

 `r"(^r[0-9]+d[0-9]\w*)"` => this will be parsed as "(^r[0-9]+d[0-9]\w*)" in the python code, r2d2\c3po will be caught.

This is why you must pay attention to the pattern showed in example and provide something identical. 

### New repositories
If you enter a new *repo_name*.ini with a repository not existing actually in the server, the service may fail.
If you enter a new *Team* in the ini that is not existing actually in the server, the service may fail.
