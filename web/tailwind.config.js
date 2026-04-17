export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      colors: {
        surface: '#F8FAFC',
        panel: '#FFFFFF',
        brand: '#2563EB',
        brandSoft: '#DBEAFE',
        text: '#1F2937',
        muted: '#64748B',
      },
      boxShadow: {
        soft: '0 18px 50px rgba(15, 23, 42, 0.06)',
      },
    },
  },
  plugins: [],
};
