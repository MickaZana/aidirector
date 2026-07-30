# Production Launch Checklist

## Pre-Launch Verification

### Accessibility
- [ ] All interactive elements keyboard-navigable
- [ ] All images/icons have `alt` or `aria-label` text
- [ ] Color contrast meets WCAG AA (4.5:1 for normal text, 3:1 for large)
- [ ] ARIA landmarks and roles on all page regions
- [ ] Focus indicators visible on all interactive elements (`focus-visible:ring-2`)
- [ ] Reduced-motion respected via `motion-safe:` prefixes
- [ ] Screen reader testing on main flows

### Responsive Layouts
- [ ] Tested at 375px (mobile)
- [ ] Tested at 768px (tablet)
- [ ] Tested at 1024px (small desktop)
- [ ] Tested at 1440px (large desktop)
- [ ] No horizontal scroll on any breakpoint
- [ ] Touch targets ≥ 44×44px on mobile

### Browser Compatibility
- [ ] Chrome (latest 2 versions)
- [ ] Firefox (latest 2 versions)
- [ ] Safari (latest 2 versions)
- [ ] Edge (latest 2 versions)
- [ ] No JavaScript console errors

### Performance
- [ ] Lighthouse Performance score ≥ 85
- [ ] Lighthouse Accessibility score ≥ 90
- [ ] First Contentful Paint (FCP) < 2s
- [ ] Largest Contentful Paint (LCP) < 2.5s
- [ ] Interaction to Next Paint (INP) < 200ms
- [ ] Bundle size reviewed (no regressions)
- [ ] Images optimized (no oversized assets)
- [ ] Font loading optimized (no layout shift)

### Error Handling
- [ ] 404 page renders correctly
- [ ] Error boundary catches unexpected errors
- [ ] API errors show user-friendly messages
- [ ] Network offline shows appropriate banner
- [ ] Upload failure shows retry option
- [ ] Processing timeout shows guidance
- [ ] Cancelled processing shows confirmation + toast
- [ ] Rate limiting handled gracefully

### Analytics
- [ ] `project_started` fires on upload page visit
- [ ] `upload_completed` fires on file selection
- [ ] `processing_started` fires on create clips click
- [ ] `processing_completed` fires on processing finish
- [ ] `clip_preview_opened` fires on clip preview
- [ ] `download_clicked` fires on clip download
- [ ] `download_all_clicked` fires on download all
- [ ] `faq_opened` fires on FAQ accordion expand
- [ ] `help_clicked` fires on help card link click
- [ ] `cancel_processing_used` fires on cancel confirm

### Feedback
- [ ] Feedback widget appears after project completion
- [ ] Rating questions functional
- [ ] Text input questions functional
- [ ] Feedback stored in localStorage
- [ ] Analytics event fires on feedback submit
- [ ] Widget dismisses after submission

### Onboarding
- [ ] First-run overlay shows on first upload page visit
- [ ] 3 steps display correctly with navigation
- [ ] Previous/Next navigation works
- [ ] Skip link dismisses overlay
- [ ] Dismissal persisted in localStorage
- [ ] Overlay does not show on subsequent visits

### Logging
- [ ] Sentry error tracking enabled
- [ ] Source maps uploaded
- [ ] Error grouping configured
- [ ] Console errors from dev code removed

### Environment Configuration
- [ ] Environment variables set in production
- [ ] API base URL configured
- [ ] Clerk publishable key configured
- [ ] Sentry DSN configured
- [ ] CSP allows all required external resources
- [ ] Stripe publishable key configured (if billing)

### Build Verification
- [ ] `npm run typecheck` passes (0 errors)
- [ ] `npm run test` passes (all tests)
- [ ] `npm run build` succeeds
- [ ] Production build starts without errors
- [ ] All routes return 200

## Deployment

- [ ] Database migrations applied (if applicable)
- [ ] Feature flags configured (if used)
- [ ] CDN cache purged
- [ ] SSL certificate valid
- [ ] Custom domain configured (if applicable)
- [ ] Monitoring dashboards set up
- [ ] Alert thresholds configured

## Post-Launch

- [ ] Smoke test all 3 screens
- [ ] Verify analytics events received
- [ ] Monitor error rates for first 24 hours
- [ ] Check feedback submissions
- [ ] Review performance data
- [ ] Test with real user traffic
- [ ] Document any issues found
