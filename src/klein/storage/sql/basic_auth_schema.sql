
CREATE TABLE session (
  session_id VARCHAR NOT NULL,
  confidential BOOLEAN NOT NULL,
  created REAL NOT NULL,
  mechanism TEXT NOT NULL,
  PRIMARY KEY (session_id)
);

CREATE TABLE account (
  account_id VARCHAR NOT NULL,
  username VARCHAR NOT NULL,
  email VARCHAR NOT NULL,
  password_blob VARCHAR NOT NULL,
  PRIMARY KEY (account_id),
  UNIQUE (username)
);

CREATE TABLE session_account (
  account_id VARCHAR,
  session_id VARCHAR,
  UNIQUE (account_id, session_id),
  FOREIGN KEY(account_id) REFERENCES account (account_id) ON DELETE CASCADE,
  FOREIGN KEY(session_id) REFERENCES session (session_id) ON DELETE CASCADE
);
