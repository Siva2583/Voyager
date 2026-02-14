const express = require('express');
const cors = require('cors');
const axios = require('axios'); 
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 4000;
app.use(cors());
app.use(express.json());
app.get('/', (req, res) => {
    res.send('VOYAGER NODE SERVER IS RUNNING');
});
app.post('/api/trip', async (req, res) => {
    try {
        const userRequest = req.body;
        console.log("1. Received request from User:", userRequest);
        console.log("2. Forwarding to Python AI...");
        const response = await axios.post('http://127.0.0.1:5000/generate', userRequest);

        console.log("3. Received data from Python:", response.data);
        res.json(response.data);

    } catch (error) {
        console.error("Error communicating with AI:", error.message);
        res.status(500).json({ error: "Failed to generate trip" });
    }
});
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
});