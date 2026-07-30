"use client";

import { useState, useCallback } from "react";
import { AppIcon } from "@/features/design-system";
import { cn } from "@/features/design-system/utils/cn";
import { motion, AnimatePresence } from "framer-motion";
import { FAQS } from "../constants/faq";
import { analytics } from "@/services/analytics";

/**
 * FAQ accordion — collapsed by default.
 * Data sourced from constants/faq.ts for easy editing.
 * Accessible: keyboard navigable, proper aria attributes.
 */
export function FAQAccordion() {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  const toggle = useCallback((index: number) => {
    const next = openIndex === index ? null : index;
    setOpenIndex(next);
    if (next !== null) {
      analytics.track("faq_opened", { questionIndex: index });
    }
  }, [openIndex]);

  return (
    <section>
      <h2 className="text-[30px] font-bold text-center text-slate-900 tracking-tight">
        Frequently Asked Questions
      </h2>
      <div className="mt-8 space-y-3">
        {FAQS.map((item, i) => {
          const isOpen = openIndex === i;
          const panelId = `faq-panel-${i}`;
          const buttonId = `faq-button-${i}`;

          return (
            <div
              key={i}
              className="rounded-2xl bg-white border border-slate-200 overflow-hidden"
            >
              <h3>
                <button
                  id={buttonId}
                  type="button"
                  onClick={() => toggle(i)}
                  aria-expanded={isOpen}
                  aria-controls={panelId}
                  className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-emerald-500/50"
                >
                  <span className="text-base font-medium text-slate-900">
                    {item.question}
                  </span>
                  <AppIcon
                    name="chevronDown"
                    size="md"
                    className={cn(
                      "shrink-0 text-slate-400 transition-transform duration-200",
                      isOpen && "rotate-180",
                    )}
                    strokeWidth={2}
                  />
                </button>
              </h3>
              <AnimatePresence initial={false}>
                {isOpen && (
                  <motion.div
                    id={panelId}
                    role="region"
                    aria-labelledby={buttonId}
                    key="panel"
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2, ease: "easeInOut" }}
                    className="overflow-hidden"
                  >
                    <div className="px-6 pb-5 text-sm text-slate-500 leading-relaxed">
                      {item.answer}
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          );
        })}
      </div>
    </section>
  );
}
