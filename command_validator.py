import re
import urllib.request
import json
from typing import List, Dict, Any

def parse_commands(text: str) -> List[Dict[str, str]]:
    """Parse terminal setup commands from script or markdown text."""
    commands = []
    if not text:
        return commands
        
    lines = text.split('\n')
    for line in lines:
        line_strip = line.strip()
        
        # Remove markdown code fence indicators
        if line_strip.startswith('```') or line_strip.endswith('```'):
            continue
            
        # Strip leading prompt symbols
        if line_strip.startswith('$ ') or line_strip.startswith('# ') or line_strip.startswith('> '):
            line_strip = line_strip[2:].strip()

            
        # 1. Match Git Clone
        git_match = re.search(r'\b(git\s+clone\s+\S+)', line_strip)
        if git_match:
            commands.append({'type': 'git', 'command': git_match.group(1)})
            
        # 2. Match Docker commands
        docker_match = re.search(r'\b(docker\s+(run|pull)\s+.*)$|\b(docker-compose\s+.*)$', line_strip)
        if docker_match:
            cmd = docker_match.group(0).strip()
            commands.append({'type': 'docker', 'command': cmd})
            
        # 3. Match Pip commands
        pip_match = re.search(r'\b(pip\d*\s+install\s+.*)$', line_strip)
        if pip_match:
            commands.append({'type': 'pip', 'command': pip_match.group(1).strip()})
            
        # 4. Match NPM commands
        npm_match = re.search(r'\b(npm\s+(install|i)\s+.*)$', line_strip)
        if npm_match:
            commands.append({'type': 'npm', 'command': npm_match.group(1).strip()})
            
        # 5. Match NPX commands
        npx_match = re.search(r'\b(npx\s+.*)$', line_strip)
        if npx_match:
            commands.append({'type': 'npx', 'command': npx_match.group(1).strip()})
            
        # 6. Match Ollama commands
        ollama_match = re.search(r'\b(ollama\s+(run|pull)\s+\S+)', line_strip)
        if ollama_match:
            commands.append({'type': 'ollama', 'command': ollama_match.group(1)})
            
        # 7. Match dangerous commands
        for bad in ['rm -rf', 'sudo', 'curl | sh', 'curl | bash', 'wget | sh', 'wget | bash', '> /dev/null']:
            if bad in line_strip:
                commands.append({'type': 'security_warning', 'command': line_strip})
                break
            
    # Deduplicate commands
    seen = set()
    deduped = []
    for cmd in commands:
        if cmd['command'] not in seen:
            seen.add(cmd['command'])
            deduped.append(cmd)
            
    return deduped


def verify_git(command: str) -> Dict[str, Any]:
    """Verify if git clone repository URL exists and is accessible."""
    parts = command.split()
    url = None
    for part in parts:
        if 'github.com' in part or 'gitlab.com' in part or part.startswith('http') or part.endswith('.git'):
            url = part
            break
            
    if not url:
        return {'status': 'warning', 'message': 'Could not extract repository URL.'}
        
    url = url.strip('"\'<>')
    if not url.startswith('http'):
        url = 'https://' + url
        
    # Clean .git suffix if present
    if url.endswith('.git'):
        url = url[:-4]
        
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0 (DailyDex Setup Validator)'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status in [200, 301, 302]:
                return {'status': 'verified', 'message': 'Repository URL is accessible.'}
    except Exception as e:
        return {'status': 'failed', 'message': f'Repository not accessible: {e}'}
        
    return {'status': 'warning', 'message': 'Validation status unclear.'}

def verify_docker(command: str) -> Dict[str, Any]:
    """Verify if docker image exists on Docker Hub Registry."""
    if 'docker-compose' in command:
        return {'status': 'skipped', 'message': 'docker-compose relies on local config, skipped verification.'}
        
    parts = command.split()
    image = None
    if len(parts) > 2:
        args = parts[2:]
        skip_next = False
        for arg in args:
            if skip_next:
                skip_next = False
                continue
            if arg.startswith('-'):
                # Handle flags with arguments
                if arg in ['-p', '-v', '-e', '-u', '--name', '--network', '--volumes-from', '--entrypoint', '--workdir', '--env-file']:
                    skip_next = True
                continue
            image = arg
            break
            
    if not image:
        # Fallback to simple scan
        for p in parts:
            if '/' in p and not p.startswith('-'):
                image = p
                break
                
    if not image:
        return {'status': 'warning', 'message': 'Could not parse Docker image name.'}
        
    image = image.strip('"\'')
    image_base = image.split(':')[0]
    
    if '/' not in image_base:
        registry_url = f'https://hub.docker.com/v2/repositories/library/{image_base}/'
    else:
        registry_url = f'https://hub.docker.com/v2/repositories/{image_base}/'
        
    try:
        req = urllib.request.Request(registry_url, method='GET', headers={'User-Agent': 'Mozilla/5.0 (DailyDex Setup Validator)'})
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                return {'status': 'verified', 'message': f'Image "{image}" exists on Docker Hub.'}
    except Exception as e:
        return {'status': 'failed', 'message': f'Docker image "{image}" not found: {e}'}
        
    return {'status': 'warning', 'message': 'Docker verification status unclear.'}

def verify_pip(command: str) -> Dict[str, Any]:
    """Verify if pip packages exist on PyPI registry."""
    parts = command.split()
    packages = []
    skip_next = False
    for part in parts[2:]:
        if skip_next:
            skip_next = False
            continue
        if part.startswith('-'):
            if part in ['-r', '-c', '-t']:
                skip_next = True
            continue
        # Split version specifiers like django==4.2 or numpy>=1.2
        pkg = re.split(r'[=<>~!]', part)[0]
        if pkg:
            packages.append(pkg)
            
    if not packages:
        return {'status': 'warning', 'message': 'No PyPI package names parsed.'}
        
    results = []
    for pkg in packages:
        url = f'https://pypi.org/pypi/{pkg}/json'
        try:
            req = urllib.request.Request(url, method='GET', headers={'User-Agent': 'Mozilla/5.0 (DailyDex Setup Validator)'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status == 200:
                    results.append((pkg, True))
        except Exception:
            results.append((pkg, False))
            
    failed = [r[0] for r in results if not r[1]]
    if failed:
        return {'status': 'failed', 'message': f'Package(s) not found on PyPI: {", ".join(failed)}'}
    return {'status': 'verified', 'message': f'All package(s) verified on PyPI: {", ".join(packages)}'}

def verify_npm(command: str) -> Dict[str, Any]:
    """Verify if NPM packages exist on NPM registry."""
    parts = command.split()
    packages = []
    for part in parts[2:]:
        if part.startswith('-'):
            continue
        # Split scope and version specifiers
        pkg = part.split('@')[0] if not part.startswith('@') else '@' + part[1:].split('@')[0]
        if pkg:
            packages.append(pkg)
            
    if not packages:
        return {'status': 'warning', 'message': 'No NPM package names parsed.'}
        
    results = []
    for pkg in packages:
        # Registry URL (support scoped packages)
        clean_pkg = pkg.replace('/', '%2F')
        url = f'https://registry.npmjs.org/{clean_pkg}'
        try:
            req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': 'Mozilla/5.0 (DailyDex Setup Validator)'})
            with urllib.request.urlopen(req, timeout=4) as resp:
                if resp.status in [200, 301, 302]:
                    results.append((pkg, True))
        except Exception:
            results.append((pkg, False))
            
    failed = [r[0] for r in results if not r[1]]
    if failed:
        return {'status': 'failed', 'message': f'Package(s) not found on NPM registry: {", ".join(failed)}'}
    return {'status': 'verified', 'message': f'All package(s) verified on NPM registry: {", ".join(packages)}'}

def verify_security(command: str) -> Dict[str, Any]:
    """Flag dangerous patterns or warnings in arbitrary shell commands."""
    if 'rm -rf' in command:
        return {'status': 'danger', 'message': 'Dangerous command detected! "rm -rf" recursively deletes files without asking.'}
    if 'sudo' in command:
        return {'status': 'warning', 'message': 'Command execution requires system administrator privileges (sudo).'}
    if 'curl' in command or 'wget' in command:
        return {'status': 'warning', 'message': 'Downloading and piping remote scripts directly to shell is insecure.'}
    return {'status': 'warning', 'message': 'Warning-prone syntax or I/O redirection detected.'}

def validate_command(cmd_entry: Dict[str, str]) -> Dict[str, Any]:
    """Router to validate a command entry by type."""
    cmd = cmd_entry['command']
    c_type = cmd_entry['type']
    
    if c_type == 'git':
        return verify_git(cmd)
    elif c_type == 'docker':
        return verify_docker(cmd)
    elif c_type == 'pip':
        return verify_pip(cmd)
    elif c_type == 'npm':
        return verify_npm(cmd)
    elif c_type == 'security_warning':
        return verify_security(cmd)
    
    return {'status': 'skipped', 'message': 'Skipped verification.'}

def validate_script_commands(script_content: str) -> List[Dict[str, Any]]:
    """Parse and validate all setup commands in a given script body."""
    parsed = parse_commands(script_content)
    results = []
    for entry in parsed:
        val_res = validate_command(entry)
        results.append({
            'command': entry['command'],
            'type': entry['type'],
            'status': val_res['status'],
            'message': val_res['message']
        })
    return results
