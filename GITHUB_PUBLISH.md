# GitHub publication checklist

Recommended repository: `d2dmh/Future-EPW-Generator`

## Repository

- Create an empty repository named `Future-EPW-Generator`.
- Do not initialize it with a README, `.gitignore`, or license; those files are already included here.
- Recommended visibility: Public for an open research-software release; Private if the project is not ready for public distribution.

## First push

```powershell
git init
git branch -M main
git add .
git commit -m "release: Future EPW Generator v1.0.0"
git remote add origin https://github.com/d2dmh/Future-EPW-Generator.git
git push -u origin main
```

## Release

The repository includes `.github/workflows/windows-release.yml`.

Create a GitHub release/tag named `v1.0.0`. The tag push triggers the Windows workflow, which builds:

- `FutureEPWGenerator_Setup_v1.0.0.exe`
- `FutureEPWGenerator_Setup_v1.0.0.exe.sha256`

and uploads them to the GitHub Release.

Use `RELEASE_NOTES_v1.0.0.md` as the release description.

## Do not commit

The `.gitignore` excludes build, `dist`, `release`, virtual environments, and runtime caches. Third-party EPW weather files should not be committed unless redistribution terms have been verified.
