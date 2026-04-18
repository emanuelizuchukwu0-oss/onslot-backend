const API_CONFIG = {
    // CheapDataHub uses API key authentication
    API_KEY: "POST https://www.cheapdatahub.ng/api/v1/resellers/data/purchase/",  // Get this from your CheapDataHub dashboard
    API_SECRET: "YOUR_CHEAPDATAHUB_SECRET", // Get this from your CheapDataHub dashboard
    BASE_URL: "https://cheapdatahub.ng/api/v1",
    
    // Network IDs (as specified by CheapDataHub)
    NETWORK_IDS: {
        mtn: "mtn",
        airtel: "airtel",
        glo: "glo",
        "9mobile": "9mobile"
    },
    
    // Plan IDs for data plans (CheapDataHub's cheapest SME plans)
    // Prices: MTN 1GB = ₦299, Glo 1GB = ₦280, Airtel 1GB = ₦450
    PLAN_IDS: {
        mtn: {
            200: "MTN_SME_1GB",    // 1GB plan (cheapest MTN plan)
            300: "MTN_SME_1GB",    // 1GB plan
            700: "MTN_SME_2GB",    // 2GB plan
            1024: "MTN_SME_1GB"    // 1GB plan
        },
        airtel: {
            200: "AIRTEL_1GB",     // 1GB plan
            300: "AIRTEL_1GB",     // 1GB plan
            700: "AIRTEL_2GB",     // 2GB plan
            1024: "AIRTEL_1GB"     // 1GB plan
        },
        glo: {
            200: "GLO_1GB",        // 1GB plan (cheapest at ₦280)
            300: "GLO_1GB",        // 1GB plan
            700: "GLO_2GB",        // 2GB plan
            1024: "GLO_1GB"        // 1GB plan
        }
    }
};