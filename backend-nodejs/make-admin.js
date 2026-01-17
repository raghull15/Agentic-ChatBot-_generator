// Script to make a user an admin
// Usage: node make-admin.js <email>

import mongoose from 'mongoose';
import User from './models/User.js';
import dotenv from 'dotenv';

dotenv.config();

const email = process.argv[2];

if (!email) {
    console.log('Usage: node make-admin.js <email>');
    console.log('Example: node make-admin.js admin@example.com');
    process.exit(1);
}

async function makeAdmin() {
    try {
        await mongoose.connect(process.env.MONGODB_URI);
        console.log('Connected to MongoDB');

        const user = await User.findOneAndUpdate(
            { email: email },
            { $set: { isAdmin: true } },
            { new: true }
        );

        if (user) {
            console.log(`✅ Successfully made ${user.email} an admin!`);
            console.log('User details:', {
                id: user._id,
                name: user.name,
                email: user.email,
                isAdmin: user.isAdmin
            });
        } else {
            console.log(`❌ User with email "${email}" not found.`);
        }
    } catch (error) {
        console.error('Error:', error.message);
    } finally {
        await mongoose.disconnect();
        process.exit(0);
    }
}

makeAdmin();
