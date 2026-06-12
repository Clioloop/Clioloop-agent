'use client';
import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { useRef } from 'react';
import { AlertDialog as AlertDialogPrimitive } from 'radix-ui';
import { cn } from '../../utils';
import { Button } from './button';
function WarningTriangle({ className }) {
    return (_jsxs("svg", { "aria-hidden": true, className: className, fill: "none", stroke: "currentColor", strokeLinecap: "round", strokeLinejoin: "round", strokeWidth: 2, viewBox: "0 0 24 24", children: [_jsx("path", { d: "m10.29 3.86-8.16 14a2 2 0 0 0 1.73 3h16.28a2 2 0 0 0 1.73-3l-8.16-14a2 2 0 0 0-3.46 0z" }), _jsx("line", { x1: "12", x2: "12", y1: "9", y2: "13" }), _jsx("line", { x1: "12", x2: "12.01", y1: "17", y2: "17" })] }));
}
export function ConfirmDialog({ cancelLabel = 'Cancel', confirmLabel = 'Confirm', description, destructive = false, loading = false, onCancel, onConfirm, open, title }) {
    const confirmedRef = useRef(false);
    return (_jsx(AlertDialogPrimitive.Root, { onOpenChange: v => {
            if (!v && !confirmedRef.current)
                onCancel();
            confirmedRef.current = false;
        }, open: open, children: _jsxs(AlertDialogPrimitive.Portal, { children: [_jsx(AlertDialogPrimitive.Overlay, { className: cn('fixed inset-0 z-50', 'bg-black/60 backdrop-blur-sm', 'data-[state=open]:animate-in data-[state=open]:fade-in-0', 'data-[state=closed]:animate-out data-[state=closed]:fade-out-0') }), _jsxs(AlertDialogPrimitive.Content, { className: cn('fixed top-1/2 left-1/2 z-50 -translate-x-1/2 -translate-y-1/2', 'w-[calc(100%-2rem)] max-w-md', 'border border-midground/15 bg-background-base text-foreground-base shadow-lg outline-none', 'data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95', 'data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=closed]:zoom-out-95', 'duration-150'), children: [_jsxs("div", { className: "flex items-start gap-3 p-4 border-b border-midground/15", children: [destructive && (_jsx("div", { "aria-hidden": true, className: "mt-0.5 shrink-0 text-destructive", children: _jsx(WarningTriangle, { className: "h-4 w-4" }) })), _jsxs("div", { className: "flex-1 min-w-0 flex flex-col gap-1", children: [_jsx(AlertDialogPrimitive.Title, { className: "font-expanded text-sm font-bold tracking-[0.08em] uppercase", children: title }), description && (_jsx(AlertDialogPrimitive.Description, { className: "font-mondwest text-xs text-midground/60 leading-relaxed", children: description }))] })] }), _jsxs("div", { className: "flex items-center justify-end gap-2 p-3", children: [_jsx(AlertDialogPrimitive.Cancel, { asChild: true, children: _jsx(Button, { disabled: loading, outlined: true, type: "button", children: cancelLabel }) }), _jsx(AlertDialogPrimitive.Action, { asChild: true, children: _jsx(Button, { destructive: destructive, disabled: loading, onClick: () => {
                                            confirmedRef.current = true;
                                            onConfirm();
                                        }, type: "button", children: loading ? '…' : confirmLabel }) })] })] })] }) }));
}
