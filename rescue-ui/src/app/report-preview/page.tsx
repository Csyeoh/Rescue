"use client";

import React, { useMemo, useState } from 'react';
import Link from 'next/link';
import { AnimatePresence } from 'motion/react';
import { MissionReportModal } from '../../components/Report/MissionReportModal';
import { mockMissionReport } from '../../components/Report/mockMissionReport';

export default function ReportPreviewPage() {
  const [isOpen, setIsOpen] = useState(true);
  const report = useMemo(() => mockMissionReport, []);

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 p-6">
      <div className="mx-auto max-w-3xl space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-semibold">Mission Report Preview</h1>
          <Link href="/" className="text-sm text-slate-300 hover:text-white underline underline-offset-4">
            Back to dashboard
          </Link>
        </div>

        <div className="rounded-2xl border border-slate-800 bg-slate-900/60 p-5">
          <p className="text-sm text-slate-300">
            Opens the report modal using mock telemetry data (no mission run required).
          </p>

          <div className="mt-4 flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => setIsOpen(true)}
              className="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-semibold"
            >
              Open mock report
            </button>
            <button
              type="button"
              onClick={() => setIsOpen(false)}
              className="px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-white text-sm font-semibold"
            >
              Close
            </button>
          </div>
        </div>
      </div>

      <AnimatePresence>{isOpen ? <MissionReportModal report={report} onClose={() => setIsOpen(false)} /> : null}</AnimatePresence>
    </div>
  );
}

