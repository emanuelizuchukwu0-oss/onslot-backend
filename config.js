const API_CONFIG = {
    // VTU.ng uses username/password, not API keys
    USERNAME: "emanuelizuchukwu0@gmail.com",  // Your VTU.ng login email/username
    PASSWORD: "1234@//Gg%^&",  // Your VTU.ng login password
    BASE_URL: "https://vtu.ng/wp-json/api/v1/data",
    
    // Network IDs (must be lowercase as specified in the API)
    NETWORK_IDS: {
        mtn: "mtn",
        airtel: "airtel",
        glo: "glo",
        "9mobile": "etisalat"  // Note: 9mobile uses "etisalat" as network_id
    },
    
    // Variation IDs for data plans [citation:2][citation:3]
    VARIATION_IDS: {
        mtn: {
            200: "M1024",    // 1GB is the smallest MTN SME plan available
            300: "M1024",    // 1GB plan for 300MB requests
            700: "M1024"     // 1GB plan for 700MB requests
            // Note: VTU.ng's smallest MTN plan is 1GB (M1024)
            // You cannot buy 200MB/300MB/700MB separately
        },
        airtel: {
            200: "AIR1000",   // Airtel 1.5GB - 30 Days [citation:2]
            300: "AIR1000",   // 1.5GB plan for 300MB requests
            700: "AIR2500"    // Airtel 6GB - 30 Days [citation:2]
        },
        glo: {
            200: "G500",      // Glo 1GB - 14 Days [citation:2]
            300: "G1000",     // Glo 2GB/2.5GB - 30 Days [citation:2]
            700: "G2000"      // Glo 5.8GB - 30 Days [citation:2]
        }
    }
};