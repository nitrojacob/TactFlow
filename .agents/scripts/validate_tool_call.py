#!/usr/bin/env python3
import sys
import json
import re
import shlex
import os

def is_destructive(command_line):
    # Split the command line by shell separators to inspect each subcommand
    try:
        subcommands = re.split(r';|&&|\|\||\||\n', command_line)
    except Exception:
        subcommands = [command_line]

    for subcmd in subcommands:
        subcmd = subcmd.strip()
        if not subcmd:
            continue
        
        try:
            tokens = shlex.split(subcmd)
        except ValueError:
            tokens = subcmd.split()
            
        if not tokens:
            continue
            
        # The command executable name
        cmd_name = os.path.basename(tokens[0])
        
        # 1. Check for rm commands
        if cmd_name == 'rm':
            has_recursive = False
            has_force = False
            targets = []
            
            for token in tokens[1:]:
                if token.startswith('-'):
                    if token.startswith('--'):
                        if token == '--recursive':
                            has_recursive = True
                        elif token == '--force':
                            has_force = True
                    else:
                        for char in token[1:]:
                            if char in ('r', 'R'):
                                has_recursive = True
                            elif char == 'f':
                                has_force = True
                else:
                    targets.append(token)
            
            # Check targets
            for target in targets:
                # Normalize targets
                normalized = os.path.normpath(target)
                if target in ('/', '/*') or normalized == '/':
                    return True, "Deletion of the root directory '/' is blocked."
                # Protect .git directory
                if '.git' in target.split('/') or target == '.git':
                    return True, "Deletion of '.git' repository metadata is blocked."
                # Protect the .agents directory itself
                if '.agents' in target.split('/') or target == '.agents':
                    return True, "Deletion of '.agents' configuration directory is blocked."

        # 2. Check for git commands affecting history
        elif cmd_name == 'git':
            if len(tokens) > 1:
                git_subcmd = tokens[1]
                
                # git reset
                if git_subcmd == 'reset':
                    for token in tokens[2:]:
                        # Block --hard reset as it discards commits and working tree changes
                        if token == '--hard':
                            return True, "git reset --hard is blocked to protect commit history."
                        # Block reset to previous commits (HEAD~, HEAD^, hashes)
                        if (token.startswith('HEAD~') or 
                            token.startswith('HEAD^') or 
                            re.match(r'^[0-9a-fA-F]{4,40}$', token)):
                            return True, f"git reset targeting '{token}' is blocked to protect commit history."
                
                # git rebase
                elif git_subcmd == 'rebase':
                    return True, "git rebase is blocked to prevent rewriting commit history."
                
                # git push with force
                elif git_subcmd == 'push':
                    for token in tokens[2:]:
                        if token in ('-f', '--force', '--force-with-lease'):
                            return True, f"git push with '{token}' is blocked to prevent overwriting history."
                        if token.startswith('+') and not token.startswith('--'):
                            return True, f"git push with force-ref '{token}' is blocked."
                
                # git filter-branch / filter-repo
                elif git_subcmd in ('filter-branch', 'filter-repo'):
                    return True, f"git {git_subcmd} is blocked as it rewrites commit history."
                
                # git branch deletion (-d / -D)
                elif git_subcmd == 'branch':
                    for token in tokens[2:]:
                        if token.startswith('-'):
                            for char in token[1:]:
                                if char in ('d', 'D'):
                                    return True, "Deleting git branches is blocked to protect commit history."

                # git commit --amend
                elif git_subcmd == 'commit':
                    for token in tokens[2:]:
                        if token == '--amend':
                            return True, "git commit --amend is blocked to protect commit history."

    # Direct substring checks as a fallback safety net
    normalized_cmd = " ".join(command_line.split())
    if "rm -rf /" in normalized_cmd or "rm -fr /" in normalized_cmd or "rm -r -f /" in normalized_cmd:
        return True, "Deletion of root directory '/' is blocked."
    if "rm -rf .git" in normalized_cmd or "rm -fr .git" in normalized_cmd or "rm -r -f .git" in normalized_cmd:
        return True, "Deletion of '.git' repository metadata is blocked."
    if "git reset --hard" in normalized_cmd:
        return True, "git reset --hard is blocked to protect commit history."
    if "git rebase" in normalized_cmd:
        return True, "git rebase is blocked to protect commit history."
    if "git push" in normalized_cmd and ("--force" in normalized_cmd or " -f" in normalized_cmd):
        return True, "Force pushing is blocked to prevent overwriting history."
    if "git filter-branch" in normalized_cmd or "git filter-repo" in normalized_cmd:
        return True, "Rewriting history with filter-branch or filter-repo is blocked."

    return False, ""

def main():
    try:
        # Read the stdin JSON payload
        input_data = sys.stdin.read()
        if not input_data.strip():
            # If input is empty, allow by default
            print(json.dumps({"decision": "allow"}))
            sys.exit(0)
            
        payload = json.loads(input_data)
        
        tool_call = payload.get("toolCall", {})
        tool_name = tool_call.get("name", "")
        
        # We only validate run_command tool calls
        if tool_name == "run_command":
            args = tool_call.get("args", {})
            # Look for CommandLine or command key
            command_line = args.get("CommandLine") or args.get("command")
            
            if command_line:
                blocked, reason = is_destructive(command_line)
                if blocked:
                    # Output JSON rejection and write to stderr
                    print(reason, file=sys.stderr)
                    print(json.dumps({
                        "decision": "deny",
                        "reason": reason
                    }))
                    sys.exit(0)
                    
        # Otherwise allow
        print(json.dumps({"decision": "allow"}))
        sys.exit(0)
        
    except Exception as e:
        # In case of any unexpected errors, print to stderr and deny to be safe
        print(f"Error in validation hook: {str(e)}", file=sys.stderr)
        print(json.dumps({
            "decision": "deny",
            "reason": f"Validation hook error: {str(e)}"
        }))
        sys.exit(0)

if __name__ == "__main__":
    main()
