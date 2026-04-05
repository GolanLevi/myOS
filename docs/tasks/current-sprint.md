# Current Sprint

## Goal
Turn the working secretary core into a safer, cleaner, more controllable system with a real web control plane.

## Current priority
- preserve existing working behavior
- improve deployment and state management
- make configuration GitOps-friendly
- keep runtime secrets outside developer-visible paths

## Definition of done for current work
- desired-state config is versioned
- local secret/provider config is not committed
- adding/removing operators is config-driven
- production runtime does not depend on developer accounts
