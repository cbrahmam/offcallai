module.exports = function override(config, env) {
  // Disable source maps in production
  if (env === 'production') {
    config.devtool = false;
  }
  
  // Remove console.log in production
  if (env === 'production') {
    config.optimization.minimizer[0].options.terserOptions.compress.drop_console = true;
  }
  
  return config;
};
