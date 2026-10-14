insert into crawl_sources (lender, url) values
    ('Kotak Mahindra Bank', 'https://www.kotak.com/en/personal-banking/loans/personal-loan/eligibility.html'),
    ('Bajaj Finance', 'https://www.bajajfinserv.in/personal-loan-eligibility-and-documents')
on conflict (url) do nothing;
