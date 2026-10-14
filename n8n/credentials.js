const env = process.env;

const credentials = [
  {
    id: "loanEnginePg001",
    name: "Loan Engine Postgres",
    type: "postgres",
    data: {
      host: env.DB_HOST,
      port: Number(env.DB_PORT),
      database: env.DB_NAME,
      user: env.DB_USER,
      password: env.DB_PASSWORD,
      ssl: env.DB_SSL,
      allowUnauthorizedCerts: env.DB_SSL === "require",
    },
  },
  {
    id: "loanEngineAi001",
    name: "Loan Engine OpenAI",
    type: "openAiApi",
    data: { apiKey: env.OPENAI_API_KEY },
  },
  {
    id: "loanEngineSes01",
    name: "Loan Engine SES",
    type: "aws",
    data: {
      region: env.AWS_REGION,
      accessKeyId: env.SES_ACCESS_KEY_ID,
      secretAccessKey: env.SES_SECRET_ACCESS_KEY,
    },
  },
];

process.stdout.write(JSON.stringify(credentials));
