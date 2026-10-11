// ==============================================================================
//  File: apps/web/src/components/SchedulePreviewModal.tsx
//  Description: F6 replan preview modal shell (legacy); body lives in SchedulePreviewPanelContent.
//  Component: Replan Preview
//  Version: 1.1
//  Created: 2026-10-09
//  Last Update: 2026-10-11
// ==============================================================================

import type { SchedulePreviewOut, StaleCategory, Task } from "../api";
import { Modal } from "./Modal";
import { SchedulePreviewPanelContent } from "./SchedulePreviewPanelContent";

export interface SchedulePreviewModalProps {
  open: boolean;
  preview: SchedulePreviewOut | null;
  loading: boolean;
  applying: boolean;
  applyError: { message: string; code?: string; staleCategories?: StaleCategory[] } | null;
  tasksById: ReadonlyMap<string, Task>;
  onClose: () => void;
  onRefresh: () => void;
  onApply: () => void;
}

export function SchedulePreviewModal({
  open,
  preview,
  loading,
  applying,
  applyError,
  tasksById,
  onClose,
  onRefresh,
  onApply,
}: SchedulePreviewModalProps) {
  return (
    <Modal
      open={open}
      title="Preview schedule changes"
      onClose={onClose}
      className="schedule-preview-modal"
    >
      <SchedulePreviewPanelContent
        preview={preview}
        loading={loading}
        applying={applying}
        applyError={applyError}
        tasksById={tasksById}
        onClose={onClose}
        onRefresh={onRefresh}
        onApply={onApply}
        layout="modal"
      />
    </Modal>
  );
}
