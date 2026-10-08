CREATE TABLE IF NOT EXISTS public.lab_marker (
    id integer PRIMARY KEY,
    marker text NOT NULL
);
INSERT INTO public.lab_marker (id, marker)
VALUES (1, 'lab-20261008-001')
ON CONFLICT (id) DO UPDATE SET marker = EXCLUDED.marker;
