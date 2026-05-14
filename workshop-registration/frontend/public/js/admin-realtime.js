var SUPABASE_URL = document.querySelector('meta[name="supabase-url"]').content;
var SUPABASE_ANON_KEY = document.querySelector('meta[name="supabase-anon-key"]').content;

var sb = supabase.createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
  realtime: { worker: true }
});

sb.channel('admin-registrants')
  .on('postgres_changes', { event: '*', schema: 'public', table: 'registrants_realtime' },
    function () {
      fetch('/api/admin/registrants')
        .then(function (r) { return r.json(); })
        .then(function (data) {
          renderRegistrantTable(data.registrants);
          renderStats(data);
        });
    })
  .subscribe();

fetch('/api/admin/registrants')
  .then(function (r) { return r.json(); })
  .then(function (data) {
    renderRegistrantTable(data.registrants);
    renderStats(data);
  });
