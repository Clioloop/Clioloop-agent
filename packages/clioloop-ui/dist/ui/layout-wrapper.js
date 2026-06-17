import { jsx as _jsx } from "react/jsx-runtime";
export function LayoutWrapper({ children }) {
    return (_jsx("html", { lang: "en", children: _jsx("body", { className: "text-text-primary bg-black antialiased", children: children }) }));
}
