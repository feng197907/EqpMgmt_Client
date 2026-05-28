Set-Location 'D:\EquipmentManagement_client'
Write-Host 'Current directory:' (Get-Location)
Write-Host 'Git status (short):'
git status --short
$porcelain = git status --porcelain
if ($porcelain) {
    Write-Host 'Staging all changes...'
    git add -A
    Write-Host 'Committing...'
    git commit -m "chore: remove deployment/docs/tests; update Windows packaging"
} else {
    Write-Host 'No changes to commit.'
}
# Ensure origin remote
$remotes = git remote
if ($remotes -notmatch 'origin') {
    Write-Host "Adding origin: git@github.com:feng197907/EqpMgmt_Client.git"
    git remote add origin git@github.com:feng197907/EqpMgmt_Client.git
} else {
    Write-Host 'Origin exists. Setting URL to the provided one.'
    git remote set-url origin git@github.com:feng197907/EqpMgmt_Client.git
}
# Force branch name
Write-Host 'Setting branch to main...'
git branch -M main
# Push
Write-Host 'Pushing to origin main...'
$push = git push -u origin main
Write-Host 'Push finished with exit code' $LASTEXITCODE
