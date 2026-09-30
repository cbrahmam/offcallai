#!/usr/bin/env node
/**
 * Test script for OffCall Node.js SDK
 *
 * Usage:
 *   node test_node_sdk.js <api_key> [endpoint]
 *
 * Example:
 *   node test_node_sdk.js ofc_test123
 *   node test_node_sdk.js ofc_test123 http://localhost:8000/api/v1/errors/ingest/js
 */

const OffCall = require('./javascript/offcall-node.js');

async function testSDK(apiKey, endpoint) {
  console.log('='.repeat(60));
  console.log('OffCall Node.js SDK Test');
  console.log('='.repeat(60));

  // Initialize SDK
  const config = {
    apiKey: apiKey,
    environment: 'test',
    release: '1.0.0-test',
    service: 'sdk-test-node',
    debug: true,
  };

  if (endpoint) {
    config.endpoint = endpoint;
  }

  console.log('\n1. Initializing SDK...');
  console.log(`   API Key: ${apiKey.substring(0, 10)}...`);
  console.log(`   Endpoint: ${endpoint || 'default'}`);

  OffCall.init(config);
  console.log('   ✓ SDK initialized');

  // Test user context
  console.log('\n2. Setting user context...');
  OffCall.setUser({
    id: 'test-user-node-789',
    email: 'node-test@example.com',
    name: 'Node Test User',
  });
  console.log('   ✓ User context set');

  // Test tags
  console.log('\n3. Setting tags...');
  OffCall.setTags({
    test_run: 'true',
    sdk_version: '1.0.0',
    runtime: 'node',
  });
  console.log('   ✓ Tags set');

  // Test breadcrumb
  console.log('\n4. Adding breadcrumb...');
  OffCall.addBreadcrumb({
    type: 'default',
    category: 'test',
    message: 'Test breadcrumb from Node.js',
    data: { action: 'sdk_test' },
  });
  console.log('   ✓ Breadcrumb added');

  // Test capture_message
  console.log('\n5. Sending test message...');
  await OffCall.captureMessage(
    'SDK test message - this is a test from the Node.js SDK',
    'info'
  );
  console.log('   ✓ Message sent');

  // Wait a moment for async send
  await new Promise((r) => setTimeout(r, 500));

  // Test capture_exception
  console.log('\n6. Sending test exception...');
  try {
    throw new Error('SDK test exception - this is a test error from Node.js SDK');
  } catch (e) {
    await OffCall.captureException(e);
  }
  console.log('   ✓ Exception sent');

  // Wait for sends to complete
  await new Promise((r) => setTimeout(r, 1000));

  console.log('\n' + '='.repeat(60));
  console.log('Test complete!');
  console.log('='.repeat(60));
  console.log('\nIf you see "[OffCall] Error reported" messages above, the SDK is working.');
  console.log('Check your OffCall dashboard to verify errors appear in Error Tracking.');
}

// Main
const args = process.argv.slice(2);
if (args.length < 1) {
  console.log('Usage: node test_node_sdk.js <api_key> [endpoint]');
  console.log('\nExample:');
  console.log('  node test_node_sdk.js ofc_your_api_key');
  console.log('  node test_node_sdk.js ofc_your_api_key http://localhost:8000/api/v1/errors/ingest/js');
  process.exit(1);
}

const apiKey = args[0];
const endpoint = args[1] || null;

testSDK(apiKey, endpoint).catch(console.error);
