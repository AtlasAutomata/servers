#!/usr/bin/env python3
import logging
import os
import argparse
from pathlib import Path
from typing import Sequence
from mcp.server import Server
from mcp.server.session import ServerSession
from mcp.server.stdio import stdio_server
from mcp.types import (
    ClientCapabilities,
    TextContent,
    Tool,
    ListRootsResult,
    RootsCapability,
)
from enum import Enum
import git
from pydantic import BaseModel

# Get Git credentials from environment
GIT_USERNAME = os.environ.get('GIT_USERNAME')
GIT_TOKEN = os.environ.get('GIT_TOKEN')

class GitStatus(BaseModel):
    repo_path: str

class GitDiffUnstaged(BaseModel):
    repo_path: str

class GitDiffStaged(BaseModel):
    repo_path: str

class GitDiff(BaseModel):
    repo_path: str
    target: str

class GitCommit(BaseModel):
    repo_path: str
    message: str

class GitAdd(BaseModel):
    repo_path: str
    files: list[str]

class GitReset(BaseModel):
    repo_path: str

class GitLog(BaseModel):
    repo_path: str
    max_count: int = 10

class GitCreateBranch(BaseModel):
    repo_path: str
    branch_name: str
    base_branch: str | None = None

class GitCheckout(BaseModel):
    repo_path: str
    branch_name: str

class GitShow(BaseModel):
    repo_path: str
    revision: str

class GitPush(BaseModel):
    repo_path: str
    remote: str = "origin"
    branch: str | None = None

class GitPull(BaseModel):
    repo_path: str
    remote: str = "origin"
    branch: str | None = None
    rebase: bool = False

class GitFetch(BaseModel):
    repo_path: str
    remote: str = "origin"

class GitMerge(BaseModel):
    repo_path: str
    branch: str

class GitStash(BaseModel):
    repo_path: str
    message: str | None = None

class GitStashPop(BaseModel):
    repo_path: str
    index: int = 0

class GitGetCurrentBranch(BaseModel):
    repo_path: str

class GitListBranches(BaseModel):
    repo_path: str

class GitDeleteBranch(BaseModel):
    repo_path: str
    branch_name: str
    force: bool = False

class GitListRemotes(BaseModel):
    repo_path: str

class GitAddRemote(BaseModel):
    repo_path: str
    name: str
    url: str

class GitRemoveRemote(BaseModel):
    repo_path: str
    name: str

class GitTools(str, Enum):
    STATUS = "git_status"
    DIFF_UNSTAGED = "git_diff_unstaged"
    DIFF_STAGED = "git_diff_staged"
    DIFF = "git_diff"
    COMMIT = "git_commit"
    ADD = "git_add"
    RESET = "git_reset"
    LOG = "git_log"
    CREATE_BRANCH = "git_create_branch"
    CHECKOUT = "git_checkout"
    SHOW = "git_show"
    PUSH = "git_push"
    PULL = "git_pull"
    FETCH = "git_fetch"
    MERGE = "git_merge"
    STASH = "git_stash"
    STASH_POP = "git_stash_pop"
    GET_CURRENT_BRANCH = "git_get_current_branch"
    LIST_BRANCHES = "git_list_branches"
    DELETE_BRANCH = "git_delete_branch"
    LIST_REMOTES = "git_list_remotes"
    ADD_REMOTE = "git_add_remote"
    REMOVE_REMOTE = "git_remove_remote"

def git_status(repo: git.Repo) -> str:
    status_output = repo.git.status()
    return status_output.decode('utf-8') if isinstance(status_output, bytes) else status_output

def git_diff_unstaged(repo: git.Repo) -> str:
    diff_output = repo.git.diff()
    return diff_output.decode('utf-8') if isinstance(diff_output, bytes) else diff_output

def git_diff_staged(repo: git.Repo) -> str:
    diff_output = repo.git.diff("--cached")
    return diff_output.decode('utf-8') if isinstance(diff_output, bytes) else diff_output

def git_diff(repo: git.Repo, target: str) -> str:
    diff_output = repo.git.diff(target)
    return diff_output.decode('utf-8') if isinstance(diff_output, bytes) else diff_output

def git_commit(repo: git.Repo, message: str) -> str:
    commit = repo.index.commit(message)
    return f"Changes committed successfully with hash {commit.hexsha}"

def git_add(repo: git.Repo, files: list[str]) -> str:
    repo.index.add(files)
    return "Files staged successfully"

def git_reset(repo: git.Repo) -> str:
    repo.index.reset()
    return "All staged changes reset"

def git_log(repo: git.Repo, max_count: int = 10) -> list[str]:
    commits = list(repo.iter_commits(max_count=max_count))
    log = []
    for commit in commits:
        log.append(
            f"Commit: {commit.hexsha}\n"
            f"Author: {commit.author}\n"
            f"Date: {commit.authored_datetime}\n"
            f"Message: {commit.message}\n"
        )
    return log

def git_create_branch(repo: git.Repo, branch_name: str, base_branch: str | None = None) -> str:
    if base_branch:
        try:
            base = repo.heads[base_branch]
        except (IndexError, AttributeError):
            raise ValueError(f"Branch '{base_branch}' not found")
    else:
        base = repo.active_branch

    # Create the new branch
    new_branch = repo.create_head(branch_name, base)
    base_name = base.name.decode('utf-8') if isinstance(base.name, bytes) else base.name
    branch_name_str = branch_name.decode('utf-8') if isinstance(branch_name, bytes) else branch_name
    return f"Created branch '{branch_name_str}' from '{base_name}'"

def git_checkout(repo: git.Repo, branch_name: str) -> str:
    repo.git.checkout(branch_name)
    return f"Switched to branch '{branch_name}'"

def git_show(repo: git.Repo, revision: str) -> str:
    commit = repo.commit(revision)
    output = [
        f"Commit: {commit.hexsha}\n"
        f"Author: {commit.author}\n"
        f"Date: {commit.authored_datetime}\n"
        f"Message: {commit.message}\n"
    ]
    if commit.parents:
        parent = commit.parents[0]
        diff = parent.diff(commit, create_patch=True)
    else:
        diff = commit.diff(git.NULL_TREE, create_patch=True)
    for d in diff:
        a_path = d.a_path.decode('utf-8') if isinstance(d.a_path, bytes) else d.a_path
        b_path = d.b_path.decode('utf-8') if isinstance(d.b_path, bytes) else d.b_path
        diff_content = d.diff.decode('utf-8') if isinstance(d.diff, bytes) else d.diff
        output.append(f"\n--- {a_path}\n+++ {b_path}\n")
        output.append(diff_content)
    return "".join(output)

def git_push(repo: git.Repo, remote: str = "origin", branch: str | None = None) -> str:
    remote_obj = repo.remote(remote)
    
    # Configure credentials if using HTTPS
    if remote_obj.url.startswith('https://') and GIT_USERNAME and GIT_TOKEN:
        with repo.git.custom_environment(GIT_USERNAME=GIT_USERNAME, GIT_PASSWORD=GIT_TOKEN):
            if branch:
                remote_obj.push(branch)
                return f"Pushed changes to {remote}/{branch}"
            else:
                remote_obj.push()
                return f"Pushed changes to {remote}"
    else:
        # Using SSH or no credentials provided
        if branch:
            remote_obj.push(branch)
            return f"Pushed changes to {remote}/{branch}"
        else:
            remote_obj.push()
            return f"Pushed changes to {remote}"

def git_pull(repo: git.Repo, remote: str = "origin", branch: str | None = None, rebase: bool = False) -> str:
    remote_obj = repo.remote(remote)
    
    # Configure Git to use rebase or merge strategy
    with repo.config_writer() as config:
        if rebase:
            config.set_value("pull", "rebase", "true")
        else:
            config.set_value("pull", "rebase", "false")
    
    try:
        # Configure credentials if using HTTPS
        if remote_obj.url.startswith('https://') and GIT_USERNAME and GIT_TOKEN:
            with repo.git.custom_environment(GIT_USERNAME=GIT_USERNAME, GIT_PASSWORD=GIT_TOKEN):
                if branch:
                    repo.git.pull(remote, branch)
                    strategy = "rebased" if rebase else "merged"
                    return f"Pulled and {strategy} changes from {remote}/{branch}"
                else:
                    repo.git.pull()
                    strategy = "rebased" if rebase else "merged"
                    return f"Pulled and {strategy} changes from {remote}"
        else:
            # Using SSH or no credentials provided
            if branch:
                repo.git.pull(remote, branch)
                strategy = "rebased" if rebase else "merged"
                return f"Pulled and {strategy} changes from {remote}/{branch}"
            else:
                repo.git.pull()
                strategy = "rebased" if rebase else "merged"
                return f"Pulled and {strategy} changes from {remote}"
    except git.GitCommandError as e:
        if "resolve your current index first" in str(e):
            raise ValueError("Cannot pull: You have unstaged changes. Please commit or stash them first.")
        elif "automatic merge failed" in str(e):
            raise ValueError("Pull failed: Merge conflicts detected. Please resolve conflicts manually.")
        raise e

def git_fetch(repo: git.Repo, remote: str = "origin") -> str:
    remote_obj = repo.remote(remote)
    
    # Configure credentials if using HTTPS
    if remote_obj.url.startswith('https://') and GIT_USERNAME and GIT_TOKEN:
        with repo.git.custom_environment(GIT_USERNAME=GIT_USERNAME, GIT_PASSWORD=GIT_TOKEN):
            remote_obj.fetch()
            return f"Fetched changes from {remote}"
    else:
        # Using SSH or no credentials provided
        remote_obj.fetch()
        return f"Fetched changes from {remote}"

def git_merge(repo: git.Repo, branch: str) -> str:
    current = repo.active_branch
    try:
        # Try to find branch in local heads first
        try:
            merge_branch = repo.heads[branch]
        except (IndexError, AttributeError):
            # If not found locally, try to find in remote refs
            try:
                merge_branch = repo.refs[branch]
            except (IndexError, AttributeError):
                raise ValueError(f"Branch '{branch}' not found")
        
        # Perform the merge
        repo.git.merge(merge_branch, '--no-ff')
        return f"Merged {branch} into {current}"
    except git.GitCommandError as e:
        if "automatic merge failed" in str(e):
            repo.git.merge('--abort')
            raise ValueError("Merge failed due to conflicts. Merge aborted.")
        raise e

def git_stash(repo: git.Repo, message: str | None = None) -> str:
    if message:
        repo.git.stash('save', message)
        return f"Stashed changes with message: {message}"
    else:
        repo.git.stash()
        return "Stashed changes"

def git_stash_pop(repo: git.Repo, index: int = 0) -> str:
    repo.git.stash('pop', f'stash@{{{index}}}')
    return f"Popped stash at index {index}"

def git_get_current_branch(repo: git.Repo) -> str:
    return str(repo.active_branch)

def git_list_branches(repo: git.Repo) -> list[str]:
    return [str(branch) for branch in repo.heads]

def git_delete_branch(repo: git.Repo, branch_name: str, force: bool = False) -> str:
    if force:
        repo.git.branch('-D', branch_name)
    else:
        repo.git.branch('-d', branch_name)
    return f"Deleted branch {branch_name}"

def git_list_remotes(repo: git.Repo) -> list[str]:
    return [f"{remote.name} ({remote.url})" for remote in repo.remotes]

def git_add_remote(repo: git.Repo, name: str, url: str) -> str:
    repo.create_remote(name, url)
    return f"Added remote {name} with URL {url}"

def git_remove_remote(repo: git.Repo, name: str) -> str:
    try:
        remote = repo.remote(name)
        # Get the Remote object from the name
        remote_obj = next(r for r in repo.remotes if r.name == name)
        repo.delete_remote(remote_obj)
        return f"Removed remote {name}"
    except (ValueError, StopIteration):
        raise ValueError(f"Remote '{name}' not found")

async def serve(repository: Path | None) -> None:
    logger = logging.getLogger(__name__)

    if repository is not None:
        try:
            git.Repo(repository)
            logger.info(f"Using repository at {repository}")
        except git.InvalidGitRepositoryError:
            logger.error(f"{repository} is not a valid Git repository")
            return

    server = Server("mcp-git")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name=GitTools.STATUS,
                description="Shows the working tree status",
                inputSchema=GitStatus.schema(),
            ),
            Tool(
                name=GitTools.DIFF_UNSTAGED,
                description="Shows changes in the working directory that are not yet staged",
                inputSchema=GitDiffUnstaged.schema(),
            ),
            Tool(
                name=GitTools.DIFF_STAGED,
                description="Shows changes that are staged for commit",
                inputSchema=GitDiffStaged.schema(),
            ),
            Tool(
                name=GitTools.DIFF,
                description="Shows differences between branches or commits",
                inputSchema=GitDiff.schema(),
            ),
            Tool(
                name=GitTools.COMMIT,
                description="Records changes to the repository",
                inputSchema=GitCommit.schema(),
            ),
            Tool(
                name=GitTools.ADD,
                description="Adds file contents to the staging area",
                inputSchema=GitAdd.schema(),
            ),
            Tool(
                name=GitTools.RESET,
                description="Unstages all staged changes",
                inputSchema=GitReset.schema(),
            ),
            Tool(
                name=GitTools.LOG,
                description="Shows the commit logs",
                inputSchema=GitLog.schema(),
            ),
            Tool(
                name=GitTools.CREATE_BRANCH,
                description="Creates a new branch from an optional base branch",
                inputSchema=GitCreateBranch.schema(),
            ),
            Tool(
                name=GitTools.CHECKOUT,
                description="Switches branches",
                inputSchema=GitCheckout.schema(),
            ),
            Tool(
                name=GitTools.SHOW,
                description="Shows the contents of a commit",
                inputSchema=GitShow.schema(),
            ),
            Tool(
                name=GitTools.PUSH,
                description="Push changes to remote repository",
                inputSchema=GitPush.schema(),
            ),
            Tool(
                name=GitTools.PULL,
                description="Pull changes from remote repository",
                inputSchema=GitPull.schema(),
            ),
            Tool(
                name=GitTools.FETCH,
                description="Fetch changes from remote without merging",
                inputSchema=GitFetch.schema(),
            ),
            Tool(
                name=GitTools.MERGE,
                description="Merge a branch into current branch",
                inputSchema=GitMerge.schema(),
            ),
            Tool(
                name=GitTools.STASH,
                description="Stash current changes",
                inputSchema=GitStash.schema(),
            ),
            Tool(
                name=GitTools.STASH_POP,
                description="Pop stashed changes",
                inputSchema=GitStashPop.schema(),
            ),
            Tool(
                name=GitTools.GET_CURRENT_BRANCH,
                description="Get name of current branch",
                inputSchema=GitGetCurrentBranch.schema(),
            ),
            Tool(
                name=GitTools.LIST_BRANCHES,
                description="List all branches",
                inputSchema=GitListBranches.schema(),
            ),
            Tool(
                name=GitTools.DELETE_BRANCH,
                description="Delete a branch",
                inputSchema=GitDeleteBranch.schema(),
            ),
            Tool(
                name=GitTools.LIST_REMOTES,
                description="List remote repositories",
                inputSchema=GitListRemotes.schema(),
            ),
            Tool(
                name=GitTools.ADD_REMOTE,
                description="Add a new remote repository",
                inputSchema=GitAddRemote.schema(),
            ),
            Tool(
                name=GitTools.REMOVE_REMOTE,
                description="Remove a remote repository",
                inputSchema=GitRemoveRemote.schema(),
            )
        ]

    async def list_repos() -> Sequence[str]:
        async def by_roots() -> Sequence[str]:
            if not isinstance(server.request_context.session, ServerSession):
                raise TypeError("server.request_context.session must be a ServerSession")

            if not server.request_context.session.check_client_capability(
                ClientCapabilities(roots=RootsCapability())
            ):
                return []

            roots_result: ListRootsResult = await server.request_context.session.list_roots()
            logger.debug(f"Roots result: {roots_result}")
            repo_paths = []
            for root in roots_result.roots:
                path = root.uri.path
                try:
                    git.Repo(path)
                    repo_paths.append(str(path))
                except git.InvalidGitRepositoryError:
                    pass
            return repo_paths

        def by_commandline() -> Sequence[str]:
            return [str(repository)] if repository is not None else []

        cmd_repos = by_commandline()
        root_repos = await by_roots()
        return [*root_repos, *cmd_repos]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict) -> list[TextContent]:
        repo_path = Path(arguments["repo_path"])
        repo = git.Repo(repo_path)

        match name:
            case GitTools.STATUS:
                status = git_status(repo)
                return [TextContent(
                    type="text",
                    text=f"Repository status:\n{status}"
                )]

            case GitTools.DIFF_UNSTAGED:
                diff = git_diff_unstaged(repo)
                return [TextContent(
                    type="text",
                    text=f"Unstaged changes:\n{diff}"
                )]

            case GitTools.DIFF_STAGED:
                diff = git_diff_staged(repo)
                return [TextContent(
                    type="text",
                    text=f"Staged changes:\n{diff}"
                )]

            case GitTools.DIFF:
                diff = git_diff(repo, arguments["target"])
                return [TextContent(
                    type="text",
                    text=f"Diff with {arguments['target']}:\n{diff}"
                )]

            case GitTools.COMMIT:
                result = git_commit(repo, arguments["message"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.ADD:
                result = git_add(repo, arguments["files"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.RESET:
                result = git_reset(repo)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.LOG:
                log = git_log(repo, arguments.get("max_count", 10))
                return [TextContent(
                    type="text",
                    text="Commit history:\n" + "\n".join(log)
                )]

            case GitTools.CREATE_BRANCH:
                result = git_create_branch(
                    repo,
                    arguments["branch_name"],
                    arguments.get("base_branch")
                )
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.CHECKOUT:
                result = git_checkout(repo, arguments["branch_name"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.SHOW:
                result = git_show(repo, arguments["revision"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.PUSH:
                result = git_push(repo, arguments.get("remote", "origin"), arguments.get("branch"))
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.PULL:
                result = git_pull(
                    repo,
                    arguments.get("remote", "origin"),
                    arguments.get("branch"),
                    arguments.get("rebase", False)
                )
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.FETCH:
                result = git_fetch(repo, arguments.get("remote", "origin"))
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.MERGE:
                result = git_merge(repo, arguments["branch"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.STASH:
                result = git_stash(repo, arguments.get("message"))
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.STASH_POP:
                result = git_stash_pop(repo, arguments.get("index", 0))
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.GET_CURRENT_BRANCH:
                result = git_get_current_branch(repo)
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.LIST_BRANCHES:
                branches = git_list_branches(repo)
                return [TextContent(
                    type="text",
                    text="Branches:\n" + "\n".join(branches)
                )]

            case GitTools.DELETE_BRANCH:
                result = git_delete_branch(repo, arguments["branch_name"], arguments.get("force", False))
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.LIST_REMOTES:
                remotes = git_list_remotes(repo)
                return [TextContent(
                    type="text",
                    text="Remotes:\n" + "\n".join(remotes)
                )]

            case GitTools.ADD_REMOTE:
                result = git_add_remote(repo, arguments["name"], arguments["url"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case GitTools.REMOVE_REMOTE:
                result = git_remove_remote(repo, arguments["name"])
                return [TextContent(
                    type="text",
                    text=result
                )]

            case _:
                raise ValueError(f"Unknown tool: {name}")

    options = server.create_initialization_options()
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, options, raise_exceptions=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Git MCP Server")
    parser.add_argument("--repository", type=Path, help="Path to Git repository")
    args = parser.parse_args()
    
    import asyncio
    asyncio.run(serve(args.repository))
