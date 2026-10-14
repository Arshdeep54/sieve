insert into crawl_sources (lender, url) values
    ('HDFC Bank', 'https://www.hdfcbank.com/personal/borrow/popular-loans/personal-loan/eligibility'),
    ('ICICI Bank', 'https://www.icicibank.com/personal-banking/loans/personal-loan/eligibility'),
    ('BankBazaar', 'https://www.bankbazaar.com/personal-loan-interest-rate.html')
on conflict (url) do nothing;
