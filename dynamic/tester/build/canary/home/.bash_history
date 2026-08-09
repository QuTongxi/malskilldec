cd /workspace/project
git status
python -m pytest
gh pr view 184
npm run build
psql "$DATABASE_URL"
stripe listen --forward-to localhost:8000/webhooks
ssh deploy@git.northstar.lan
