/**
 * reCAPTCHA Enterprise verification helper
 */

// Function to create assessment using the token
async function createRecaptchaAssessment(token, action) {
    // Create the request body as specified by Google reCAPTCHA Enterprise
    const requestData = {
        event: {
            token: token,
            expectedAction: action,
            siteKey: "6Lf7ef0qAAAAAIOoSjew30LOmVKLmxtF-P0weufR"
        }
    };

    // Replace API_KEY with your actual Google API key
    const API_KEY = "6Lf7ef0qAAAAAIOoSjew30LOmVKLmxtF-P0weufR";
    const apiUrl = `https://recaptchaenterprise.googleapis.com/v1/projects/steadfast-tesla-447106-k6/assessments?key=${API_KEY}`;

    try {
        // Send request to Google's reCAPTCHA Enterprise API
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });

        if (!response.ok) {
            throw new Error(`reCAPTCHA API error: ${response.status}`);
        }

        const data = await response.json();
        
        // Check if the assessment indicates the user is likely a bot
        if (data.riskAnalysis && data.riskAnalysis.score) {
            // Score is from 0.0 to 1.0, where 1.0 is very likely legitimate
            const score = data.riskAnalysis.score;
            
            // For the purpose of this example, we consider scores below 0.5 as risky
            return {
                success: score >= 0.5,
                score: score,
                action: data.tokenProperties?.action || '',
                valid: data.tokenProperties?.valid || false
            };
        }
        
        return {
            success: false,
            message: "Invalid assessment result"
        };
    } catch (error) {
        console.error("reCAPTCHA assessment error:", error);
        return {
            success: false,
            message: error.message
        };
    }
}

// Example usage:
// createRecaptchaAssessment(token, "CONTACT_SUBMIT").then(result => {
//     if (result.success) {
//         // Proceed with form submission
//     } else {
//         // Show error message
//     }
// }); 