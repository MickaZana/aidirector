# Backup & Recovery Procedures

## Overview

Backup and recovery strategy for the AI Director beta. This document covers all data stores, configuration, and infrastructure components.

**RPO (Recovery Point Objective):** 24 hours  
**RTO (Recovery Time Objective):** 4 hours  
**Last tested:** —

---

## 1. Data Stores

### 1.1 PostgreSQL Database (Neon)

**Backup method:** Neon automated daily backups + point-in-time recovery (PITR)

```bash
# List available backups
neon backup list --project aidirector

# Manual backup (pre-deploy)
neon backup create --project aidirector --name "pre-deploy-$(date +%Y%m%d)"

# Restore to a branch (for verification)
neon branch create --project aidirector --source main --name "restore-test"
```

**Automation:**
- [ ] Neon automatic daily backup enabled (retention: 7 days)
- [ ] Pre-deploy manual backup script: `scripts/backup-db.sh`
- [ ] PITR window: 24 hours (Neon free tier → 7 days on paid)

**Recovery steps:**
```bash
# 1. Create restore branch from latest backup
neon branch create --project aidirector \
  --source main \
  --name "recovery-$(date +%Y%m%d-%H%M)"

# 2. Update DATABASE_URL in production to point to restore branch
# 3. Run pending migrations (if any)
cd apps/api && uv run alembic upgrade head
# 4. Verify data integrity with smoke test
# 5. Update DATABASE_URL back to main branch once recovery is verified
```

### 1.2 Redis (Upstash)

**Backup method:** Redis is ephemeral state (job queues, cache). No persistent backup needed.

**Recovery:**
- Worker queues auto-recover when workers reconnect
- Cache will be rebuilt naturally
- No action needed; restart Redis and workers will drain remaining jobs

**If Redis is unrecoverable:**
```bash
# 1. Reset all queues
redis-cli -u "$REDIS_URL" FLUSHALL

# 2. Restart workers
docker compose -f docker-compose.prod.yml restart worker

# 3. Jobs in "queued" state will be re-enqueued by the API
```

### 1.3 Object Storage (R2)

**Backup method:** R2 is the primary storage. No built-in cross-region replication on free tier.

**Mitigation:**
- Original uploaded files are retained until the tenant deletes them or retention policy triggers
- Exported clips are reproducible from originals (re-run pipeline)
 **Backup critical data manually:**
```bash
# Backup presign records (R2 keys)
aws s3 sync s3://aidirector-prod/ ./backups/r2/ \
  --endpoint-url https://<account_id>.r2.cloudflarestorage.com

# Restore
aws s3 sync ./backups/r2/ s3://aidirector-prod/ \
  --endpoint-url https://<account_id>.r2.cloudflarestorage.com
```

### 1.4 Analytics (localStorage)

**Backup method:** Not backed up. Analytics data is non-critical, non-PII, and stored ephemerally in user browsers.

**Recovery:** No action needed. Data collection resumes automatically.

---

## 2. Configuration Backups

### 2.1 Environment Variables

```bash
# Backup all .env files (excluding .env.local)
cp .env.example backups/env/example.env
# Vercel project env vars: export from Vercel dashboard
# GitHub Actions secrets: stored in GitHub, not locally backed up

# Document all production env vars in a secure vault (e.g., 1Password)
```

**Automation:**
- [ ] `.env.example` is the source of truth for all required vars
- [ ] Production env vars documented in team vault
- [ ] Vercel project env vars importable via Vercel CLI

### 2.2 Infrastructure (Pulumi)

```bash
# Pulumi state is managed by Pulumi Cloud
# State file: pulumi.com/aidirector/prod

# Export stack for offline backup
pulumi stack export --file backups/infra/prod-$(date +%Y%m%d).json
```

**Automation:**
- [ ] Pulumi stack export weekly
- [ ] Pulumi state versioned in Pulumi Cloud

---

## 3. Application Backups

### 3.1 CI/CD Configuration

- GitHub Actions workflows are versioned in the repository
- `.github/workflows/` is covered by git history
- No separate backup needed

### 3.2 Docker Images

```bash
# List current images
docker images aidirector/*

# Save images to tar
docker save aidirector/api:latest -o backups/images/api-latest.tar
docker save aidirector/worker:latest -o backups/images/worker-latest.tar

# Load from tar
docker load -i backups/images/api-latest.tar
```

**Automation:**
- [ ] Docker images tagged with git SHA + `latest`
- [ ] Previous image always available for rollback
- [ ] Images cached by Docker Hub or container registry (if configured)

---

## 4. Recovery Scenarios

### Scenario A: Database Corruption

**Symptoms:** API returning 500 errors, health/db failing, data inconsistency

**Steps:**
1. **Immediate:** Take API offline (return maintenance page)
   ```
   vercel env add NEXT_PUBLIC_MAINTENANCE_MODE true
   ```
2. **Diagnose:** Check Neon dashboard for corruption scope
3. **Restore:** Point API to Neon backup branch (see 1.1)
4. **Verify:** Run smoke tests (health, upload flow, job creation)
5. **Switch:** Update DATABASE_URL → restored branch
6. **Root cause:** Investigate migration or data write that caused corruption

### Scenario B: Complete Infrastructure Failure

**Symptoms:** All services down, no access to deployment platform

**Steps:**
1. **Declare incident** — notify team
2. **Restore DNS** — point to static maintenance page (Vercel)
3. **Rebuild from backup:**
   ```bash
   # Restore Pulumi state
   pulumi stack import --file backups/infra/prod-20260730.json
   pulumi up

   # Restore database
   # (Create new Neon project from backup)

   # Deploy API
   docker compose -f docker-compose.prod.yml up -d

   # Deploy frontend
   vercel deploy --prod

   # Verify all health endpoints
   ```
4. **Stage rollback** — if rebuild fails, switch to pre-production environment

### Scenario C: Accidental Data Deletion

**Symptoms:** User reports missing uploads, jobs, or exported clips

**Steps:**
1. **Identify scope:** Which tenant, which entities, when
2. **Database:** Restore affected rows from Neon PITR (branch from before deletion time)
3. **R2:** Restore deleted objects from backup (or re-upload originals)
4. **Verify:** Confirm data restored for affected tenant
5. **Notify:** Inform user data has been restored

### Scenario D: Security Incident

**Symptoms:** Unauthorized access detected, suspicious activity, data breach

**Steps:**
1. **Isolate:** Rotate all secrets immediately
   ```bash
   # Rotate Clerk keys
   # Rotate Stripe keys
   # Rotate R2 keys
   # Rotate Database credentials
   ```
2. **Snapshot:** Capture logs and database state for forensics
3. **Contain:** Temporarily disable API access if needed
4. **Analyze:** Review access logs, identify entry point
5. **Notify:** Legal/compliance notification (72-hour GDPR requirement)
6. **Remediate:** Fix vulnerability, restore from pre-incident backup
7. **Verify:** Confirm fix effective, re-enable access

---

## 5. Backup Schedule

| Asset | Frequency | Retention | Automated | Tool |
|-------|-----------|-----------|-----------|------|
| Database | Daily (auto) | 7 days | ✅ | Neon backups |
| Database | Pre-deploy | Until next backup | ⚠️ Manual | `scripts/backup-db.sh` |
| R2 storage | On-demand | Indefinite | ❌ | `aws s3 sync` |
| Environment vars | Per change | Indefinite | ❌ | Vault |
| Pulumi state | Weekly | 4 weeks | ⚠️ Manual | `pulumi stack export` |

---

## 6. Recovery Drills

Schedule quarterly recovery drills to verify procedures:

- [ ] **Q1 2026:** Restore database from backup (Scenario A)
- [ ] **Q2 2026:** Rebuild from scratch (Scenario B)
- **Due:** Q3 2026 (before scaling beta)

### Drill Template

```
## Recovery Drill Report

**Date:** YYYY-MM-DD
**Scenario:** [A/B/C/D]
**Duration:** [actual time]
**RTO met?** [Yes/No]

### Steps taken
1. ...
2. ...

### Issues encountered
- ...

### Improvements needed
- ...

### Next drill date:
```
