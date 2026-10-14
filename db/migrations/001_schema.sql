create table upload_batches (
    batch_id      uuid primary key,
    s3_key        text not null,
    etag          text,
    status        text not null default 'pending'
                  check (status in ('pending', 'ingesting', 'ingested', 'matching', 'matched',
                                    'notifying', 'done', 'duplicate', 'failed')),
    duplicate_of  uuid references upload_batches (batch_id),
    total_rows    integer,
    valid_rows    integer,
    rejected_rows integer,
    errors_key    text,
    error         text,
    execution_id  text,
    created_at    timestamptz not null default now(),
    updated_at    timestamptz not null default now()
);

create unique index upload_batches_live_etag
    on upload_batches (etag)
    where status not in ('duplicate', 'failed');

create table users (
    user_id           uuid primary key,
    name              text,
    email             text not null,
    monthly_income    integer not null check (monthly_income > 0),
    credit_score      smallint not null check (credit_score between 300 and 900),
    employment_status text not null check (employment_status in ('salaried', 'self_employed', 'business')),
    age               smallint not null check (age between 18 and 100),
    batch_id          uuid not null references upload_batches (batch_id),
    created_at        timestamptz not null default now(),
    updated_at        timestamptz not null default now()
);

create index users_batch_id on users (batch_id);

create table crawl_sources (
    source_id serial primary key,
    lender    text not null,
    url       text not null unique,
    is_active boolean not null default true
);

create table crawl_runs (
    run_id         bigserial primary key,
    source_id      integer not null references crawl_sources (source_id),
    http_status    integer,
    content_hash   text,
    changed        boolean,
    products_found integer,
    status         text not null check (status in ('unchanged', 'updated', 'empty', 'failed')),
    error          text,
    created_at     timestamptz not null default now()
);

create index crawl_runs_source_latest on crawl_runs (source_id, created_at desc);

create table loan_products (
    product_id            serial primary key,
    source_id             integer not null references crawl_sources (source_id),
    lender                text not null,
    product_name          text not null,
    source_url            text not null,
    interest_rate_min     numeric(5, 2),
    interest_rate_max     numeric(5, 2),
    min_monthly_income    integer,
    min_credit_score      smallint,
    max_credit_score      smallint,
    min_age               smallint,
    max_age               smallint,
    employment_types      text[],
    qualitative_criteria  text,
    max_amount            bigint,
    max_tenure_months     smallint,
    processing_fee        text,
    extraction_confidence numeric(3, 2),
    criteria_hash         text not null,
    version               integer not null default 1,
    is_active             boolean not null default true,
    is_matchable          boolean generated always as (
                              min_monthly_income is not null or min_credit_score is not null
                          ) stored,
    first_seen_at         timestamptz not null default now(),
    last_seen_at          timestamptz not null default now(),
    unique (source_id, lender, product_name)
);

create table matches (
    user_id     uuid not null references users (user_id),
    product_id  integer not null references loan_products (product_id),
    batch_id    uuid not null references upload_batches (batch_id),
    stage       text not null check (stage in ('sql', 'cache', 'llm')),
    verdict     text not null check (verdict in ('eligible', 'likely')),
    score       numeric(4, 3) not null,
    reason      text not null,
    created_at  timestamptz not null default now(),
    notified_at timestamptz,
    primary key (user_id, product_id)
);

create index matches_batch_pending on matches (batch_id) where notified_at is null;

create unlogged table match_candidates (
    batch_id   uuid not null,
    user_id    uuid not null,
    product_id integer not null,
    class_key  text not null,
    score      numeric(4, 3) not null,
    reason     text not null,
    primary key (batch_id, user_id, product_id)
);

create table llm_eval_cache (
    product_id      integer not null references loan_products (product_id),
    product_version integer not null,
    class_key       text not null,
    verdict         text not null check (verdict in ('eligible', 'likely', 'ineligible')),
    reason          text not null,
    created_at      timestamptz not null default now(),
    primary key (product_id, product_version, class_key)
);

create table match_runs (
    batch_id         uuid primary key references upload_batches (batch_id),
    users_in_batch   integer not null,
    products_active  integer not null,
    pairs_total      integer not null,
    pairs_after_sql  integer not null,
    sql_matches      integer not null,
    pairs_deferred   integer not null,
    classes_to_judge integer not null,
    cache_hits       integer not null,
    llm_calls        integer not null,
    llm_matches      integer not null,
    total_matches    integer not null,
    duration_ms      integer not null,
    created_at       timestamptz not null default now()
);

create table notifications (
    notification_id bigserial primary key,
    user_id         uuid not null references users (user_id),
    batch_id        uuid not null references upload_batches (batch_id),
    to_address      text,
    product_ids     integer[] not null,
    status          text not null check (status in ('sent', 'suppressed', 'failed')),
    ses_message_id  text,
    created_at      timestamptz not null default now(),
    unique (user_id, batch_id)
);

create table workflow_errors (
    error_id   bigserial primary key,
    workflow   text not null,
    node       text,
    message    text not null,
    batch_id   uuid,
    created_at timestamptz not null default now()
);
