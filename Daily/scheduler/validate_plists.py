#!/usr/bin/env python3
"""
Validate India-TS plist integrity and check for cross-project contamination
This script ensures proper namespace separation and plist consistency
"""

import os
import subprocess
import glob
import hashlib
import json
from datetime import datetime
import plistlib

def get_file_hash(filepath):
    """Calculate MD5 hash of a file"""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def validate_namespace(plist_path):
    """Check if plist uses correct namespace"""
    filename = os.path.basename(plist_path)
    
    # India-TS files must start with com.india-ts
    if 'india-ts' in plist_path.lower() or 'India-TS' in plist_path:
        return filename.startswith('com.india-ts.')
    
    # US-TS files must start with com.us-ts
    if 'us-ts' in plist_path.lower() or 'US-TS' in plist_path:
        return filename.startswith('com.us-ts.')
    
    return True  # Unknown project, pass validation

def check_plist_content(plist_path):
    """Validate plist content and structure"""
    try:
        with open(plist_path, 'rb') as f:
            plist_data = plistlib.load(f)
        
        # Check required keys
        required_keys = ['Label', 'ProgramArguments']
        missing_keys = [key for key in required_keys if key not in plist_data]
        
        if missing_keys:
            return False, f"Missing required keys: {missing_keys}"
        
        # Check Label matches filename
        expected_label = os.path.basename(plist_path).replace('.plist', '')
        if plist_data['Label'] != expected_label:
            return False, f"Label mismatch: {plist_data['Label']} != {expected_label}"
        
        return True, "Valid"
    except Exception as e:
        return False, f"Parse error: {str(e)}"

def main():
    """Validate all plist files"""
    
    # Define paths
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backup_dir = os.path.join(script_dir, 'plists')
    installed_dir = '/Users/maverick/Library/LaunchAgents'
    
    print("India-TS Plist Validation Report")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Find all plist files
    all_plists = glob.glob(os.path.join(installed_dir, '*.plist'))
    india_plists = [p for p in all_plists if 'com.india-ts.' in os.path.basename(p)]
    us_plists = [p for p in all_plists if 'com.us-ts.' in os.path.basename(p)]
    other_plists = [p for p in all_plists if p not in india_plists + us_plists]
    
    print(f"Found {len(all_plists)} total plist files:")
    print(f"  - India-TS: {len(india_plists)}")
    print(f"  - US-TS: {len(us_plists)}")
    print(f"  - Other: {len(other_plists)}")
    print()
    
    # Check for namespace violations
    print("Namespace Validation:")
    print("-" * 40)
    violations = []
    
    for plist in india_plists:
        if not validate_namespace(plist):
            violations.append(plist)
    
    if violations:
        print("✗ NAMESPACE VIOLATIONS FOUND:")
        for v in violations:
            print(f"  - {os.path.basename(v)}")
    else:
        print("✓ All India-TS plists use correct namespace")
    print()
    
    # Compare backup vs installed
    print("Backup Integrity Check:")
    print("-" * 40)
    
    backup_plists = glob.glob(os.path.join(backup_dir, 'com.india-ts.*.plist'))
    backup_names = {os.path.basename(p) for p in backup_plists}
    installed_names = {os.path.basename(p) for p in india_plists}
    
    # Missing from backup
    missing_backup = installed_names - backup_names
    if missing_backup:
        print("✗ Installed but not in backup:")
        for m in sorted(missing_backup):
            print(f"  - {m}")
    else:
        print("✓ All installed plists are backed up")
    
    # Missing from installed
    missing_installed = backup_names - installed_names
    if missing_installed:
        print("✗ In backup but not installed:")
        for m in sorted(missing_installed):
            print(f"  - {m}")
    else:
        print("✓ All backup plists are installed")
    print()
    
    # Check file integrity
    print("File Integrity Check:")
    print("-" * 40)
    
    integrity_issues = []
    for backup_path in backup_plists:
        filename = os.path.basename(backup_path)
        installed_path = os.path.join(installed_dir, filename)
        
        if os.path.exists(installed_path):
            backup_hash = get_file_hash(backup_path)
            installed_hash = get_file_hash(installed_path)
            
            if backup_hash != installed_hash:
                integrity_issues.append({
                    'file': filename,
                    'backup_hash': backup_hash,
                    'installed_hash': installed_hash
                })
    
    if integrity_issues:
        print("✗ File differences detected:")
        for issue in integrity_issues:
            print(f"  - {issue['file']}")
            print(f"    Backup:    {issue['backup_hash']}")
            print(f"    Installed: {issue['installed_hash']}")
    else:
        print("✓ All files match backup")
    print()
    
    # Check plist content validity
    print("Content Validation:")
    print("-" * 40)
    
    content_issues = []
    for plist_path in india_plists:
        valid, message = check_plist_content(plist_path)
        if not valid:
            content_issues.append({
                'file': os.path.basename(plist_path),
                'issue': message
            })
    
    if content_issues:
        print("✗ Content issues found:")
        for issue in content_issues:
            print(f"  - {issue['file']}: {issue['issue']}")
    else:
        print("✓ All plists have valid content")
    print()
    
    # Check job status
    print("Job Status Check:")
    print("-" * 40)
    
    loaded_count = 0
    not_loaded = []
    
    for plist_path in india_plists:
        job_id = os.path.basename(plist_path).replace('.plist', '')
        result = subprocess.run(['launchctl', 'list', job_id], 
                              capture_output=True, text=True)
        
        if result.returncode == 0:
            loaded_count += 1
        else:
            not_loaded.append(job_id)
    
    print(f"✓ Loaded: {loaded_count}/{len(india_plists)} jobs")
    if not_loaded:
        print("✗ Not loaded:")
        for job in not_loaded:
            print(f"  - {job}")
    print()
    
    # Generate summary report
    report = {
        'timestamp': datetime.now().isoformat(),
        'total_plists': len(all_plists),
        'india_ts_count': len(india_plists),
        'us_ts_count': len(us_plists),
        'namespace_violations': len(violations),
        'missing_backups': list(missing_backup),
        'missing_installed': list(missing_installed),
        'integrity_issues': len(integrity_issues),
        'content_issues': len(content_issues),
        'loaded_jobs': loaded_count,
        'not_loaded_jobs': not_loaded
    }
    
    # Save report
    report_path = os.path.join(script_dir, 'plist_validation_report.json')
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"Full report saved to: {report_path}")
    
    # Return status
    issues_found = (violations or missing_backup or missing_installed or 
                   integrity_issues or content_issues or not_loaded)
    
    if issues_found:
        print("\n⚠️  ISSUES FOUND - Please review and fix")
        return 1
    else:
        print("\n✅ ALL VALIDATIONS PASSED")
        return 0

if __name__ == '__main__':
    exit(main())