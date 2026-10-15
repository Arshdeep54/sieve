alter table upload_batches
    add column file_name   text,
    add column uploaded_by text;

create index upload_batches_created_at on upload_batches (created_at desc);
