import os
import subprocess
import sys
from pathlib import Path

def run_modal(args):
    cmd = ["uv", "run", "modal"] + args
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, check=True)

def parse_env(path: Path) -> dict:
    env = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip().strip("'").strip('"')
    return env

def main():
    root = Path(__file__).parent.parent
    env_file = root / ".env.local"
    
    if not env_file.exists():
        print(f"Error: {env_file} does not exist.")
        sys.exit(1)
        
    env = parse_env(env_file)
    
    # Check for modal token
    if not env.get("MODAL_TOKEN_ID") or not env.get("MODAL_TOKEN_SECRET"):
        print("Error: MODAL_TOKEN_ID and MODAL_TOKEN_SECRET are missing in .env.local")
        print("Run 'uv run modal token new' to generate them, then add them to .env.local")
        sys.exit(1)
        
    # Group secrets as defined in REMAINING_CONNECTIONS.md
    secrets = {
        "aidirector-db": ["DATABASE_URL"],
        "aidirector-redis": ["REDIS_URL"],
        "aidirector-r2": ["R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET"],
        "aidirector-signing": ["PROVENANCE_SIGNING_KEY_B64"],
        "aidirector-anthropic": ["ANTHROPIC_API_KEY"],
    }
    
    print("\n--- Syncing secrets to Modal ---")
    for secret_name, keys in secrets.items():
        missing = [k for k in keys if not env.get(k) or env.get(k).startswith("xxx") or env.get(k) == "sk-ant-xxx"]
        if missing:
            print(f"Skipping {secret_name} - missing or default values for: {', '.join(missing)}")
            continue
            
        args = ["secret", "create", secret_name]
        for k in keys:
            args.append(f"{k}={env.get(k)}")
            
        try:
            run_modal(args)
            print(f"Successfully synced {secret_name}\n")
        except subprocess.CalledProcessError:
            print(f"Failed to sync {secret_name}\n")

if __name__ == "__main__":
    main()
