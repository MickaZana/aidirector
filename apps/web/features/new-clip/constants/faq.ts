export interface FAQItem {
  question: string;
  answer: string;
}

/**
 * Frequently Asked Questions.
 * Edit or add entries here — they'll render in the accordion automatically.
 */
export const FAQS: FAQItem[] = [
  {
    question: "How long does processing take?",
    answer:
      "Most videos finish in only a few minutes. Longer matches naturally require more time.",
  },
  {
    question: "Do I need editing experience?",
    answer:
      "No. AI Director was built specifically for coaches and creators who have never used editing software.",
  },
  {
    question: "Can I upload a full football match?",
    answer:
      "Yes. Upload the complete recording. AI Director automatically finds the most important moments.",
  },
  {
    question: "Which platforms are supported?",
    answer:
      "YouTube Shorts, TikTok, Instagram Reels. Support for additional platforms will continue to grow.",
  },
  {
    question: "Will my original video be changed?",
    answer:
      "No. The original upload is never modified. AI Director creates new clips while leaving your original file untouched.",
  },
];
