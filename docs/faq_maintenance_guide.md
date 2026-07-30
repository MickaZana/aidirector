# FAQ Maintenance Guide

## How to Add or Edit FAQ Items

The FAQ data lives in a single constants file:

```
apps/web/features/new-clip/constants/faq.ts
```

### File Structure

```typescript
export const FAQS: FAQItem[] = [
  {
    question: "What video formats do you support?",
    answer: "We support MP4, MOV, and MKV files...",
  },
  // Add new items here
];
```

### Adding a New FAQ

1. Open `apps/web/features/new-clip/constants/faq.ts`.
2. Append a new object to the `FAQS` array with `question` and `answer` fields.
3. Keep answers concise (2–4 sentences) and written in plain language.
4. No technical jargon — users should understand without domain knowledge.

### Editing an Existing FAQ

1. Find the item in the `FAQS` array.
2. Update the `question` or `answer` field.
3. Maintain the same tone and style as existing entries.

### Style Guidelines

- **Questions** should be phrased as the user would ask them (e.g., "How long does processing take?" not "Processing duration specifications").
- **Answers** should:
  - Start with the direct answer.
  - Add 1–2 sentences of helpful context.
  - Link to the User Guide where relevant.
  - Avoid marketing language — be straightforward.

### Example

```typescript
{
  question: "Can I use AI Director on my phone?",
  answer: "AI Director is designed for desktop use. While you can view your clips on mobile, uploading and processing work best on a computer with a stable internet connection.",
}
```

### Publishing

After editing the file:
1. TypeScript type-checking will verify the structure.
2. The FAQ section on the **New Clip** page will automatically reflect changes — no additional deployment steps needed.

---

## FAQ Items Reference

| Index | Topic |
|-------|-------|
| 0 | Supported video formats |
| 1 | Estimated processing time |
| 2 | Cancelling a project |
| 3 | Clip quality factors |
| 4 | Target platform support |
| 5 | Data retention and privacy |
