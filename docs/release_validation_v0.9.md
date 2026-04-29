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

### Creator Mode
- [ ] 8. Switch variant to DailyDex Creator
- [ ] 9. Confirm Creator Brief loads first
- [ ] 10. Confirm Video Ideas, Shorts, Clusters, Research Packs, and Content Pipeline tabs are visible
- [ ] 11. Confirm creator cards show hooks, formats, titles, and thumbnail text
- [ ] 12. Confirm Build research pack creates a Markdown file
- [ ] 13. Confirm Creator Digest renders and saves successfully

### Theme
- [ ] 14. Toggle light/dark theme

### Data Operations
- [ ] 15. Click Refresh Now
- [ ] 16. Confirm source health updates
- [ ] 17. Save one item
- [ ] 18. Confirm toast appears

### Saved Board
- [ ] 19. Open Saved board
- [ ] 20. Change saved item status
- [ ] 21. Add notes/tags
- [ ] 22. Export JSON and Markdown
- [ ] 23. Test bulk actions

### Digest
- [ ] 24. Open Daily Digest
- [ ] 25. Generate/copy digest

### View Modes
- [ ] 26. Switch card/table views in GitHub
- [ ] 27. Switch card/table views in Models
- [ ] 28. Switch card/table views in Research

### Trends
- [ ] 29. Open Trends page
- [ ] 30. Confirm charts render or degrade gracefully

### Responsive
- [ ] 31. Resize browser to tablet width
- [ ] 32. Resize browser to mobile width
- [ ] 33. Confirm no horizontal overflow

### Documentation
- [ ] 34. Confirm README screenshots still match the actual UI
- [ ] 35. Confirm Docker image name and container name use dailydex

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
