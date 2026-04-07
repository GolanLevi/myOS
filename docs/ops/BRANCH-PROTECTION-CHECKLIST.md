# Branch protection checklist

Protect `main`:
- require pull request before merge
- require at least 1 approval
- require status checks if you have them
- restrict direct pushes
- do not allow force push to `main`
- optionally require code owner review

The runtime VM should track only approved `main`.
