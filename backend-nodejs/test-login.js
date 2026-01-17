// Quick script to test login and check isAdmin
import mongoose from 'mongoose';
import User from './models/User.js';
import dotenv from 'dotenv';

dotenv.config();

async function testLogin() {
    try {
        await mongoose.connect(process.env.MONGODB_URI);
        console.log('Connected to MongoDB');

        // Find the user
        const user = await User.findOne({ email: 'heloo@gmail.com' });

        if (user) {
            console.log('User found in database:');
            console.log('  ID:', user._id);
            console.log('  Name:', user.name);
            console.log('  Email:', user.email);
            console.log('  isAdmin:', user.isAdmin);
            console.log('  isAdmin type:', typeof user.isAdmin);
        } else {
            console.log('User not found!');
        }
    } catch (error) {
        console.error('Error:', error.message);
    } finally {
        await mongoose.disconnect();
        process.exit(0);
    }
}

testLogin();
