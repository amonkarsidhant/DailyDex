# DailyDex v0.9 Release Validation

Manual checklist for validating the DailyDex 0.9 release.

## Pre-Check

- [ ] Verify VERSION file contains `0.9`
- [ ] Verify README badge shows `v0.9`
- [ ] Verify sidebar navigation is visible on desktop

## Manual UI Validation

### Basic Load
- [ ] 1. Open http://localhost:8888
- [ ] 2. Confirm browser title says DailyDex
- [ ] 3. Confirm sidebar logo says DailyDex
- [ ] 4. Confirm Overview loads first

### Navigation
- [ ] 5. Confirm sidebar navigation is visible
- [ ] 6. Confirm sidebar navigation works
- [ ] 7. Confirm top search is visible

### Theme
- [ ] 8. Toggle light/dark theme

### Data Operations
- [ ] 9. Click Refresh Now
- [ ] 10. Confirm source health updates
- [ ] 11. Save one item
- [ ] 12. Confirm toast appears

### Saved Board
- [ ] 13. Open Saved board
- [ ] 14. Change saved item status
- [ ] 15. Add notes/tags
- [ ] 16. Export JSON and Markdown
- [ ] 17. Test bulk actions

### Digest
- [ ] 18. Open Daily Digest
- [ ] 19. Generate/copy digest

### View Modes
- [ ] 20. Switch card/table views in GitHub
- [ ] 21. Switch card/table views in Models
- [ ] 22. Switch card/table views in Research

### Trends
- [ ] 23. Open Trends page
- [ ] 24. Confirm charts render or degrade gracefully

### Responsive
- [ ] 25. Resize browser to tablet width
- [ ] 26. Resize browser to mobile width
- [ ] 27. Confirm no horizontal overflow

### Documentation
- [ ] 28. Confirm README screenshots still match the actual UI
- [ ] 29. Confirm Docker image name and container name use dailydex

## Release Fields

| Field | Value |
|-------|-------|
| Date | |
| Browser | |
| Tester | |
| Result | |
| Notes | |

## Validation Notes

- All items should pass for a clean release
- Any failures should be documented in Notes with severity
- Charts may degrade gracefully on mobile (no crash)
- Toast notifications confirm save/ignore operations
