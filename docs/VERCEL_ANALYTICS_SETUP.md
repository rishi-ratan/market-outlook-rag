# Vercel Web Analytics Setup

This guide explains how Vercel Web Analytics has been integrated into the Market Outlook RAG project.

## Overview

Vercel Web Analytics is enabled on this project to track visitor behavior, page views, and user interactions. This helps us understand how users are interacting with the application and identify areas for improvement.

## What Has Been Implemented

The following changes have been made to enable Vercel Web Analytics:

### 1. Package Installation

The `@vercel/analytics` package has been added to the web app dependencies:

```json
{
  "dependencies": {
    "@vercel/analytics": "^1.4.0"
  }
}
```

### 2. Analytics Component Integration

The `Analytics` component from `@vercel/analytics/next` has been integrated into the root layout (`apps/web/app/layout.tsx`):

```tsx
import { Analytics } from "@vercel/analytics/next";

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        {children}
        <Analytics />
      </body>
    </html>
  );
}
```

## Prerequisites

Before deploying to Vercel, ensure the following:

1. **Vercel Account**: You need a [Vercel account](https://vercel.com/signup) to use Web Analytics
2. **Project on Vercel**: Your project should be [deployed to Vercel](https://vercel.com/new)
3. **Vercel CLI** (optional): For local development, you can install the Vercel CLI:
   ```bash
   npm install vercel --save-dev
   # or
   yarn add --dev vercel
   # or
   pnpm add -D vercel
   ```

## Enabling Web Analytics in Vercel Dashboard

To enable Web Analytics:

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project
3. Click the **Analytics** tab
4. Click **Enable** to activate Web Analytics

> **Note**: Enabling Web Analytics will add new routes (scoped at `/_vercel/insights/*`) after your next deployment.

## Deployment

Once Web Analytics is enabled in the Vercel dashboard, you can deploy your app:

```bash
# Using Vercel CLI
vercel deploy

# Or commit to your Git repository and push to trigger automatic deployment
git push origin main
```

After deployment, the app will start tracking:
- Page views
- User interactions
- Performance metrics
- Custom events (if configured)

## Verifying Web Analytics

To verify that Web Analytics is working correctly:

1. Visit your deployed application
2. Open your browser's **Network** tab (press F12)
3. Look for requests to `/_vercel/insights/view`
4. If you see these requests, Web Analytics is tracking properly

## Viewing Analytics Data

Once your app is deployed and has received visitors:

1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project
3. Click the **Analytics** tab
4. View your data and explore metrics by filtering the panels

> **Note**: It may take a few minutes for data to appear in the dashboard after the first requests are made.

## Advanced Features

### Custom Events

Users on Pro and Enterprise plans can track custom events such as:
- Button clicks
- Form submissions
- Purchases
- Document uploads
- Feature usage

To implement custom events, import the `track` function:

```tsx
import { track } from "@vercel/analytics";

// Track a custom event
track("document_uploaded", {
  document_name: "example.pdf",
  size_mb: 2.5,
});
```

### Route Detection

The Analytics component automatically detects route changes in Next.js and tracks page views for each route.

## Environment Variables

No additional environment variables are required for basic Web Analytics functionality. The package automatically uses Vercel's infrastructure when deployed to Vercel.

## Privacy and Compliance

Vercel Web Analytics follows privacy best practices:
- No personal data is stored
- No cookies are used for tracking
- Data is compliant with GDPR, CCPA, and other privacy regulations
- For more details, see [Vercel's Privacy Policy](https://vercel.com/legal/privacy-policy)

## Troubleshooting

### Web Analytics not appearing in dashboard

- **Wait for data**: It can take a few minutes for initial data to appear
- **Check deployment**: Ensure your app is deployed to Vercel, not a different hosting provider
- **Verify routes**: Check the Network tab for `/_vercel/insights/view` requests
- **Re-enable**: Try disabling and re-enabling Web Analytics in the dashboard

### High costs

- **Review custom events**: Each custom event counts toward your plan's limits
- **Check for errors**: Ensure custom event calls are not being called excessively
- **Plan upgrade**: Consider upgrading your Vercel plan if you exceed limits

## Documentation References

For more information about Vercel Web Analytics:

- [Vercel Web Analytics Documentation](https://vercel.com/docs/analytics)
- [@vercel/analytics Package Documentation](https://github.com/vercel/analytics)
- [Analytics Package Options](https://vercel.com/docs/analytics/package)
- [Custom Events Guide](https://vercel.com/docs/analytics/custom-events)
- [Filtering Data](https://vercel.com/docs/analytics/filtering)
- [Pricing and Limits](https://vercel.com/docs/analytics/limits-and-pricing)

## Next Steps

1. Enable Web Analytics in your Vercel dashboard
2. Deploy your application to Vercel
3. Visit your application and interact with it
4. Check the Analytics tab in your dashboard to view the collected data
5. Consider implementing custom events to track specific user actions (Pro/Enterprise plans)
