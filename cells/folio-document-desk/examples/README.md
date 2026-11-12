# Synthetic fixture

`SYNTHETIC-not-a-real-invoice.pdf` was written for this cell. It is not a customer invoice, not a bank document, and not a file from Forward-Future/folio (including Folio’s own sample PDF). The page stream contains the sentence `SYNTHETIC example. Not a real invoice.`

The desk only checks that the file starts with `%PDF-` and hashes the bytes. It does not claim Folio can render this fixture; that was not tested here.
