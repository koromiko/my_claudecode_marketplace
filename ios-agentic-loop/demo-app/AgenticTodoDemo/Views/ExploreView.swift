import SwiftUI
import MapKit

struct ExploreView: View {
    @State private var viewModel = ExploreViewModel()

    private let columns = [
        GridItem(.flexible(), spacing: 12),
        GridItem(.flexible(), spacing: 12)
    ]

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Map — top half
                Map(position: $viewModel.cameraPosition) {
                    ForEach(viewModel.restaurants) { restaurant in
                        Marker(restaurant.name, systemImage: "fork.knife", coordinate: restaurant.coordinate)
                            .tint(.orange)
                    }
                }
                .mapStyle(.standard(pointsOfInterest: .excludingAll))
                .onMapCameraChange(frequency: .onEnd) { context in
                    viewModel.onRegionChange(context.region)
                }
                .accessibilityIdentifier("explore_map")

                // Grid — bottom half
                Group {
                    if viewModel.isLoading && viewModel.restaurants.isEmpty {
                        ProgressView("Finding restaurants…")
                            .frame(maxWidth: .infinity, maxHeight: .infinity)
                            .accessibilityIdentifier("explore_loading")
                    } else if let error = viewModel.errorMessage {
                        ContentUnavailableView("Something went wrong", systemImage: "exclamationmark.triangle", description: Text(error))
                            .accessibilityIdentifier("explore_error")
                    } else if viewModel.restaurants.isEmpty {
                        ContentUnavailableView("No Restaurants", systemImage: "fork.knife", description: Text("Pan the map to search a different area."))
                            .accessibilityIdentifier("explore_empty")
                    } else {
                        ScrollView {
                            LazyVGrid(columns: columns, spacing: 12) {
                                ForEach(viewModel.restaurants) { restaurant in
                                    RestaurantCard(restaurant: restaurant)
                                }
                            }
                            .padding(12)
                            .accessibilityIdentifier("explore_grid")
                        }
                    }
                }
            }
            .navigationTitle("Explore")
            .navigationBarTitleDisplayMode(.inline)
            .onAppear {
                viewModel.performInitialSearch()
            }
        }
    }
}
