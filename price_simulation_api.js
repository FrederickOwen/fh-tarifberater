const CLIENT_ID = "sb-27fb148c-fe57-4a21-8d4d-f462d0af1a34!b185136|it-rt-intense-ag-development!b117912";
const CLIENT_SECRET = "070a2839-315f-48cb-9834-b818948979e2$gDS3MxTiFCAeToiE9e5k2tQpmL6dD5SdYIS-rkQRhi4=";
const TOKEN_URL = "https://intense-ag-development.authentication.eu10.hana.ondemand.com/oauth/token";

const INTENSE_URL =
  "https://intense-ag-development.it-cpi018-rt.cfapps.eu10-003.hana.ondemand.com/http/v1/s4/upil/product/simulation";

let cachedToken = null;
let tokenExpiry = 0; 

async function fetchNewToken() {
  const raw = CLIENT_ID + ":" + CLIENT_SECRET;
  const base64 = Buffer.from(raw).toString("base64");
  const authHeader = "Basic " + base64;

  const body = "grant_type=client_credentials";

  const res = await fetch(TOKEN_URL, {
    method: "POST",
    headers: {
      "Content-Type": "application/x-www-form-urlencoded",
      "Authorization": authHeader
    },
    body
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(
      "Token request failed: " + res.status + " " + res.statusText + " - " + text
    );
  }

  const data = await res.json();
  const accessToken = data.access_token;
  const expiresInSec = data.expires_in || 3600;

  const now = Date.now();
  tokenExpiry = now + (expiresInSec - 60) * 1000;
  cachedToken = accessToken;

  log.info("PriceSimulationApi: fetched new token, expires in " + expiresInSec + "s");

  return accessToken;
}

async function getAccessToken() {
  const now = Date.now();
  if (cachedToken && now < tokenExpiry) {
    log.info("PriceSimulationApi: use cached token");
    return cachedToken;
  }
  return await fetchNewToken();
}

async function main() {
  try {
    log.info("PriceSimulationApi: started");

    const requestBody = (typeof req !== "undefined" && req.body) ? req.body : {};
    log.info("PriceSimulationApi: requestBody = " + JSON.stringify(requestBody));

    const token = await getAccessToken();
    log.info("PriceSimulationApi: got token");

    const intenseResponse = await fetch(INTENSE_URL, {
      method: "POST",
      headers: {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify(requestBody)
    });

    const text = await intenseResponse.text();
    log.info("PriceSimulationApi: INTENSE status = " + intenseResponse.status);

    if (!intenseResponse.ok) {
      throw new Error(
        "INTENSE API error: " +
        intenseResponse.status + " " + intenseResponse.statusText + " - " + text
      );
    }

    let data;
    try {
      data = JSON.parse(text);
    } catch (e) {
      data = text;
    }

    res.status(200).send(data);
    log.info("PriceSimulationApi: success, response sent");
  } catch (err) {
    log.error("PriceSimulationApi ERROR: " + err.stack);
    try {
      res.status(500).send({ error: err.message });
    } catch (e) { /* ignore if already sent */ }
  } finally {
    complete(); 
  }
}

main();
