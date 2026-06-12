'use client';
import { useCallback, useState } from 'react';
export function useConfirmDelete({ onDelete }) {
    const [pendingId, setPendingId] = useState(null);
    const [isDeleting, setIsDeleting] = useState(false);
    const requestDelete = useCallback((id) => {
        setPendingId(id);
    }, []);
    const cancel = useCallback(() => {
        if (!isDeleting)
            setPendingId(null);
    }, [isDeleting]);
    const confirm = useCallback(async () => {
        if (pendingId === null)
            return;
        const id = pendingId;
        setIsDeleting(true);
        try {
            await onDelete(id);
            setPendingId(null);
        }
        catch {
            // Dialog stays open; caller can surface errors in onDelete
        }
        finally {
            setIsDeleting(false);
        }
    }, [pendingId, onDelete]);
    return {
        cancel,
        confirm,
        isDeleting,
        isOpen: pendingId !== null,
        pendingId,
        requestDelete
    };
}
