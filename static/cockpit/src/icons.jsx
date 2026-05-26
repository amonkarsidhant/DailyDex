// Icons — minimal, line-style, 16px viewbox. Stroke 1.5.
const Icon = ({ d, size = 16, fill = "none", stroke = "currentColor", strokeWidth = 1.5, children, style }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill={fill} stroke={stroke} strokeWidth={strokeWidth}
       strokeLinecap="round" strokeLinejoin="round" style={style}>
    {d ? <path d={d} /> : children}
  </svg>
);

const I = {
  Pulse:    (p) => <Icon {...p}><path d="M1 8h3l2-5 3 10 2-5 1 2 3 0" /></Icon>,
  Brief:    (p) => <Icon {...p}><path d="M3 2.5h7l3 3V13a.5.5 0 0 1-.5.5h-9A.5.5 0 0 1 3 13V2.5Z"/><path d="M10 2.5V6h3"/><path d="M5.5 8.5h5M5.5 10.5h3"/></Icon>,
  Cluster:  (p) => <Icon {...p}><circle cx="4" cy="4" r="2"/><circle cx="12" cy="4" r="1.6"/><circle cx="12" cy="12" r="2"/><circle cx="4" cy="12" r="1.6"/><path d="M5.5 5.5l5 5M10.5 5.5l-5 5"/></Icon>,
  Thumb:    (p) => <Icon {...p}><rect x="2" y="3" width="12" height="9" rx="1"/><path d="m4 11 3-3 3 2 2-2"/><circle cx="11" cy="5.5" r="0.8"/></Icon>,
  Research: (p) => <Icon {...p}><circle cx="7" cy="7" r="4.5"/><path d="m10.5 10.5 3 3"/></Icon>,
  Pipeline: (p) => <Icon {...p}><rect x="1.5" y="3" width="3" height="10"/><rect x="6.5" y="3" width="3" height="6"/><rect x="11.5" y="3" width="3" height="8"/></Icon>,
  Calendar: (p) => <Icon {...p}><rect x="2" y="3" width="12" height="11" rx="1"/><path d="M2 6h12M5 1.5v3M11 1.5v3"/></Icon>,
  Studio:   (p) => <Icon {...p}><circle cx="8" cy="8" r="6"/><path d="M8 5.5v5M5.5 8h5"/><circle cx="8" cy="8" r="2"/></Icon>,
  Settings: (p) => <Icon {...p}><circle cx="8" cy="8" r="2"/><path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.2 3.2l1.4 1.4M11.4 11.4l1.4 1.4M3.2 12.8l1.4-1.4M11.4 4.6l1.4-1.4"/></Icon>,
  Bell:     (p) => <Icon {...p}><path d="M4 11V7a4 4 0 0 1 8 0v4l1 1.5H3L4 11Z"/><path d="M6.5 13.5a1.5 1.5 0 0 0 3 0"/></Icon>,
  Refresh:  (p) => <Icon {...p}><path d="M13.5 6.5A6 6 0 0 0 2.5 4.5"/><path d="M2.5 9.5a6 6 0 0 0 11 2"/><path d="M11 2v4h-4M5 14v-4h4"/></Icon>,
  Plus:     (p) => <Icon {...p}><path d="M8 3v10M3 8h10"/></Icon>,
  ArrowR:   (p) => <Icon {...p}><path d="M3 8h10M9 4l4 4-4 4"/></Icon>,
  ArrowUp:  (p) => <Icon {...p}><path d="M8 13V3M4 7l4-4 4 4"/></Icon>,
  ArrowDn:  (p) => <Icon {...p}><path d="M8 3v10M12 9l-4 4-4-4"/></Icon>,
  Spark:    (p) => <Icon {...p}><path d="M8 1.5l1.4 4.1L13.5 7 9.4 8.4 8 12.5 6.6 8.4 2.5 7l4.1-1.4L8 1.5Z"/></Icon>,
  Send:     (p) => <Icon {...p}><path d="m2 8 12-6-5 14-2-6-5-2Z"/></Icon>,
  Eye:      (p) => <Icon {...p}><path d="M1.5 8s2.5-5 6.5-5 6.5 5 6.5 5-2.5 5-6.5 5S1.5 8 1.5 8Z"/><circle cx="8" cy="8" r="2"/></Icon>,
  GH:       (p) => <Icon {...p} stroke="none" fill="currentColor"><path d="M8 1.5C4.4 1.5 1.5 4.4 1.5 8c0 2.9 1.9 5.3 4.5 6.2.3.1.4-.1.4-.3v-1.1c-1.8.4-2.2-.8-2.2-.8-.3-.8-.7-1-.7-1-.6-.4 0-.4 0-.4.7 0 1 .7 1 .7.6 1 1.6.7 2 .5.1-.4.2-.7.4-.9-1.4-.2-2.9-.7-2.9-3.2 0-.7.2-1.3.7-1.7 0-.2-.3-.9.1-1.8 0 0 .5-.2 1.8.7.5-.1 1.1-.2 1.6-.2.5 0 1.1.1 1.6.2 1.3-.9 1.8-.7 1.8-.7.3.9.1 1.6.1 1.8.4.4.7 1 .7 1.7 0 2.5-1.5 3-2.9 3.2.2.2.4.6.4 1.2v1.7c0 .2.1.4.4.3 2.6-.9 4.5-3.3 4.5-6.2 0-3.6-2.9-6.5-6.5-6.5Z"/></Icon>,
  HF:       (p) => <Icon {...p} stroke="none" fill="currentColor"><path d="M8 2c-3 0-5.5 2.3-5.5 5.2 0 1 .3 1.9.8 2.7-.4.4-.8.9-.8 1.4 0 .4.3.7.7.7.4 0 .8-.2 1.2-.5.3.2.6.4.9.5-.3.3-.5.7-.5 1.1 0 .5.4.9.9.9.5 0 1-.4 1.2-.9.4.1.7.1 1.1.1.4 0 .7 0 1.1-.1.2.5.7.9 1.2.9.5 0 .9-.4.9-.9 0-.4-.2-.8-.5-1.1.3-.1.6-.3.9-.5.4.3.8.5 1.2.5.4 0 .7-.3.7-.7 0-.5-.4-1-.8-1.4.5-.8.8-1.7.8-2.7C13.5 4.3 11 2 8 2Zm-2 5.5a.8.8 0 1 1 0-1.5.8.8 0 0 1 0 1.5Zm4 0a.8.8 0 1 1 0-1.5.8.8 0 0 1 0 1.5ZM6 10c.7.8 1.3 1 2 1s1.3-.2 2-1c-.5.2-1.2.3-2 .3s-1.5-.1-2-.3Z"/></Icon>,
  YT:       (p) => <Icon {...p} stroke="none" fill="currentColor"><path d="M14.5 4.7c-.2-.7-.7-1.2-1.4-1.4C11.8 3 8 3 8 3s-3.8 0-5.1.3c-.7.2-1.2.7-1.4 1.4C1.2 6 1.2 8 1.2 8s0 2 .3 3.3c.2.7.7 1.2 1.4 1.4 1.3.3 5.1.3 5.1.3s3.8 0 5.1-.3c.7-.2 1.2-.7 1.4-1.4.3-1.3.3-3.3.3-3.3s0-2-.3-3.3ZM6.5 10.3v-4.6L10.5 8l-4 2.3Z"/></Icon>,
  Doc:      (p) => <Icon {...p}><path d="M3.5 1.5h6l3 3V14.5h-9z"/><path d="M9.5 1.5v3h3"/></Icon>,
  Paper:    (p) => <Icon {...p}><path d="M2.5 2h6l3 3v9h-9z"/><path d="M8.5 2v3h3M5 8h5M5 10h5M5 12h3"/></Icon>,
  X:        (p) => <Icon {...p}><path d="M3 3l10 10M13 3 3 13"/></Icon>,
  Filter:   (p) => <Icon {...p}><path d="M2 3h12l-4.5 5.5V13l-3-1.5V8.5L2 3Z"/></Icon>,
  Save:     (p) => <Icon {...p}><path d="M3 1.5h7l3 3V14.5H3V1.5Z"/><path d="M5 1.5v4h5v-4M5 14.5V10h5v4.5"/></Icon>,
  Play:     (p) => <Icon {...p} fill="currentColor" stroke="none"><path d="M4 2.5v11l9-5.5L4 2.5Z"/></Icon>,
  Pause:    (p) => <Icon {...p} fill="currentColor" stroke="none"><rect x="4" y="3" width="3" height="10"/><rect x="9" y="3" width="3" height="10"/></Icon>,
  Trend:    (p) => <Icon {...p}><path d="M2 12 6 7l3 3 5-7"/><path d="M10 3h4v4"/></Icon>,
};

window.I = I;
window.Icon = Icon;
