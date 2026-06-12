export declare function Toast({ toast }: ToastProps): import("react").ReactPortal;
interface ToastProps {
    toast: {
        message: string;
        type: 'error' | 'success';
    } | null;
}
export {};
