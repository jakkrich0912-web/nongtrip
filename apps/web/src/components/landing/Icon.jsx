export default function Icon({ name = 'arrow', size = 20, ...props }) {
  const paths = {
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    pin: <><path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z" /><circle cx="12" cy="10" r="2.5" /></>,
    search: <><circle cx="10.5" cy="10.5" r="6.5" /><path d="m16 16 5 5" /></>,
    chat: <path d="M20 11a8 8 0 0 1-8 8H4l1.3-4A8 8 0 1 1 20 11Z" />,
    check: <path d="m5 12 4 4L19 6" />,
    cafe: <><path d="M4 8h13v6a6.5 6.5 0 0 1-13 0V8Zm13 1h2a3 3 0 1 1 0 6h-2M7 3v2m5-2v2M3 21h16" /></>,
    compass: <><circle cx="12" cy="12" r="9" /><path d="m16 8-2 6-6 2 2-6Z" /></>,
    shield: <><path d="m12 3 8 3v6c0 5-8 9-8 9s-8-4-8-9V6Z" /><path d="m8 12 3 3 5-6" /></>,
    link: <><path d="m10 13 4-4m-6 6-2 2a4 4 0 0 1-6-6l4-4a4 4 0 0 1 6 0m4 2 2-2a4 4 0 0 1 6 6l-4 4a4 4 0 0 1-6 0" transform="translate(1 0)" /></>,
    home: <path d="m3 10 9-7 9 7M5 9v12h14V9m-10 12v-7h6v7" />,
    external: <path d="M14 3h7v7m0-7L10 14M10 3H4v17h17v-6" />,
    menu: <path d="M4 6h16M4 12h16M4 18h16" />,
  };
  return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...props}>{paths[name] ?? paths.arrow}</svg>;
}
